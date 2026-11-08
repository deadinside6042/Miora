package com.miora.wellbeing

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.*

private val Ink = Color(0xFF193B39)
private val Teal = Color(0xFF438F83)
private val Mint = Color(0xFFE6F3EE)
private val Cream = Color(0xFFFAF8F2)
private val Peach = Color(0xFFF6E4D9)
private val Muted = Color(0xFF71827D)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MioraApp(this) }
    }
}

data class ChatLine(val role: String, val text: String)

@Composable
fun MioraApp(context: Context) {
    val prefs = remember { context.getSharedPreferences("miora", Context.MODE_PRIVATE) }
    var accessToken by remember { mutableStateOf(prefs.getString("access_token", "") ?: "") }
    var refreshToken by remember { mutableStateOf(prefs.getString("refresh_token", "") ?: "") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var authError by remember { mutableStateOf("") }
    var conversationId by remember { mutableStateOf(prefs.getString("conversation_id", "") ?: "") }
    var tab by remember { mutableStateOf("Home") }
    var mood by remember { mutableStateOf(prefs.getString("mood", "") ?: "") }
    var journal by remember { mutableStateOf(prefs.getString("journal", "") ?: "") }
    var savedJournal by remember { mutableStateOf(prefs.getString("journal", "") ?: "") }
    var chat by remember { mutableStateOf(listOf(ChatLine("assistant", "Hi, I’m here with you. What’s on your mind today?"))) }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf("") }
    var profileName by remember { mutableStateOf("") }
    var profileMemory by remember { mutableStateOf("") }
    var profileNotice by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(accessToken) {
        if (accessToken.isNotBlank()) {
            // Refresh first: access tokens expire, and profile/history requests
            // must not keep using an expired JWT.
            var activeAccess = accessToken
            var activeRefresh = refreshToken
            val refreshed = withContext(Dispatchers.IO) {
                refreshMioraSession(activeRefresh)
            }
            if (refreshed != null && refreshed.accessToken.isNotBlank()) {
                activeAccess = refreshed.accessToken
                activeRefresh = refreshed.refreshToken
                accessToken = activeAccess
                refreshToken = activeRefresh
                prefs.edit()
                    .putString("access_token", activeAccess)
                    .putString("refresh_token", activeRefresh)
                    .apply()
            }

            val profile = loadMioraProfile(activeAccess)
            if (profile != null) {
                profileName = profile.preferredName
                profileMemory = profile.memorySummary
            }
            val history = loadMioraHistory(activeAccess, conversationId)
            if (!history.isNullOrEmpty()) chat = history
        }
    }

    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Teal, onPrimary = Color.White, background = Cream,
            surface = Color.White, onSurface = Ink, secondary = Peach
        )
    ) {
        if (accessToken.isBlank()) {
            SignInScreen(email, { email = it }, password, { password = it }, busy, authError) {
                busy = true
                authError = ""
                scope.launch {
                    val result = withContext(Dispatchers.IO) { loginMiora(email.trim(), password) }
                    if (result.first != null) {
                        accessToken = result.first!!
                        refreshToken = result.third
                        prefs.edit().putString("access_token", accessToken).putString("refresh_token", refreshToken).apply()
                    } else authError = result.second
                    busy = false
                }
            }
        } else Scaffold(
            containerColor = Cream,
            bottomBar = {
                NavigationBar(containerColor = Color.White) {
                    listOf("Home", "Mood", "Journal", "Support", "Profile").forEach { item ->
                        NavigationBarItem(
                            selected = tab == item,
                            onClick = { tab = item },
                            icon = {
                                Icon(
                                    when(item) {
                                        "Home" -> Icons.Default.Home
                                        "Mood" -> Icons.Default.SentimentSatisfied
                                        "Journal" -> Icons.Default.EditNote
                                        "Profile" -> Icons.Default.Person
                                        else -> Icons.Default.Forum
                                    }, contentDescription = item
                                )
                            },
                            label = { Text(item) },
                            colors = NavigationBarItemDefaults.colors(selectedIconColor = Teal, indicatorColor = Mint)
                        )
                    }
                }
            }
        ) { padding ->
            Column(Modifier.fillMaxSize().padding(padding)) {
                when(tab) {
                    "Home" -> HomeScreen(mood, savedJournal, { tab = it })
                    "Mood" -> MoodScreen(mood, {
                        mood = it
                        prefs.edit().putString("mood", it).apply()
                        notice = "Mood check-in saved"
                    }, notice)
                    "Journal" -> JournalScreen(journal, { journal = it }, {
                        savedJournal = journal
                        prefs.edit().putString("journal", journal).apply()
                        notice = "Your reflection is saved on this device"
                    }, notice)
                    "Profile" -> ProfileScreen(profileName, { profileName = it }, profileMemory, { profileMemory = it }, {
                        busy = true
                        scope.launch {
                            val saved = withContext(Dispatchers.IO) { saveMioraProfile(accessToken, profileName.trim(), profileMemory.trim()) }
                            profileNotice = if (saved) "Your profile and memory are saved." else "Could not save right now. Please try again."
                            busy = false
                        }
                    }, profileNotice)
                    else -> CompanionScreen(chat, message, { message = it }, busy, { userText ->
                        chat = chat + ChatLine("user", userText)
                        message = ""
                        busy = true
                        scope.launch {
                            val result = withContext(Dispatchers.IO) { askMiora(userText, chat, accessToken, refreshToken, conversationId) }
                            accessToken = result.accessToken
                            refreshToken = result.refreshToken
                            prefs.edit().putString("access_token", accessToken).putString("refresh_token", refreshToken).apply()
                            chat = chat + ChatLine("assistant", result.reply)
                            if (result.conversationId.isNotBlank()) {
                                conversationId = result.conversationId
                                prefs.edit().putString("conversation_id", conversationId).apply()
                            }
                            busy = false
                        }
                    })
                }
            }
        }
    }
}

@Composable
fun Header(eyebrow: String, title: String, subtitle: String = "") {
    Column(Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 18.dp)) {
        Text(eyebrow.uppercase(), color = Teal, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.5.sp)
        Spacer(Modifier.height(7.dp))
        Text(title, color = Ink, fontSize = 29.sp, fontWeight = FontWeight.Bold)
        if (subtitle.isNotBlank()) {
            Spacer(Modifier.height(5.dp))
            Text(subtitle, color = Muted, fontSize = 14.sp)
        }
    }
}

@Composable
fun HomeScreen(mood: String, journal: String, navigate: (String) -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Header("A little space for you", "Welcome to Miora", "Small steps count. You can start wherever you are.")
        Card(Modifier.fillMaxWidth().padding(horizontal = 18.dp), colors = CardDefaults.cardColors(containerColor = Mint), shape = RoundedCornerShape(26.dp)) {
            Column(Modifier.padding(20.dp)) {
                Text("A gentle reminder", color = Teal, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                Spacer(Modifier.height(8.dp))
                Text("You don’t have to figure everything out today.", color = Ink, fontSize = 23.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(10.dp))
                Text("Take one breath. Then the next.", color = Muted, fontSize = 14.sp)
            }
        }
        Text("Your daily check-in", Modifier.padding(start = 22.dp, top = 24.dp, bottom = 10.dp), color = Ink, fontSize = 19.sp, fontWeight = FontWeight.Bold)
        Card(Modifier.fillMaxWidth().padding(horizontal = 18.dp), colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(22.dp)) {
            Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(if (mood.isBlank()) "How are you feeling?" else "Today you felt $mood", color = Ink, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                    Text("There’s no right or wrong answer.", color = Muted, fontSize = 13.sp)
                }
                Button(onClick = { navigate("Mood") }, shape = RoundedCornerShape(14.dp)) { Text("Check in") }
            }
        }
        Text("Make room for a thought", Modifier.padding(start = 22.dp, top = 24.dp, bottom = 10.dp), color = Ink, fontSize = 19.sp, fontWeight = FontWeight.Bold)
        Card(Modifier.fillMaxWidth().padding(horizontal = 18.dp), colors = CardDefaults.cardColors(containerColor = Peach.copy(alpha = .55f)), shape = RoundedCornerShape(22.dp)) {
            Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(if (journal.isBlank()) "A page just for you" else "Your reflection is saved", color = Ink, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                    Text("Write without needing to make it perfect.", color = Muted, fontSize = 13.sp)
                }
                IconButton(onClick = { navigate("Journal") }) { Icon(Icons.Default.ArrowForward, null, tint = Ink) }
            }
        }
        Card(Modifier.fillMaxWidth().padding(18.dp), colors = CardDefaults.cardColors(containerColor = Ink), shape = RoundedCornerShape(22.dp)) {
            Row(Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Talk it out", color = Color(0xFFB8E1D3), fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(5.dp))
                    Text("A calm, judgment-free space to untangle a thought.", color = Color.White, fontSize = 17.sp)
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = { navigate("Companion") }, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFB8E1D3), contentColor = Ink)) { Text("Chat with Miora") }
                }
                Icon(Icons.Default.Favorite, null, tint = Color(0xFFB8E1D3), modifier = Modifier.size(42.dp))
            }
        }
        Text("Miora is a wellness companion, not a substitute for professional care.", Modifier.padding(horizontal = 22.dp, vertical = 8.dp), color = Muted, fontSize = 11.sp)
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
fun MoodScreen(selected: String, onSelect: (String) -> Unit, notice: String) {
    val moods = listOf("Great" to "😊", "Good" to "🙂", "Okay" to "😐", "Low" to "😔", "Anxious" to "😟", "Overwhelmed" to "😣")
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Header("Notice, don't judge", "How are you feeling?", "Choose what feels closest. You can always change it.")
        moods.chunked(2).forEach { pair ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                pair.forEach { (name, emoji) ->
                    Card(
                        Modifier.weight(1f).padding(vertical = 6.dp).clickable { onSelect(name) },
                        colors = CardDefaults.cardColors(containerColor = if (selected == name) Mint else Color.White),
                        border = if (selected == name) BorderStroke(2.dp, Teal) else null,
                        shape = RoundedCornerShape(20.dp)
                    ) {
                        Column(Modifier.fillMaxWidth().padding(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(emoji, fontSize = 34.sp)
                            Spacer(Modifier.height(7.dp))
                            Text(name, color = Ink, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        }
        if (notice.isNotBlank()) Text(notice, Modifier.padding(22.dp), color = Teal, fontWeight = FontWeight.Medium)
        Card(Modifier.fillMaxWidth().padding(18.dp), colors = CardDefaults.cardColors(containerColor = Peach.copy(alpha = .5f)), shape = RoundedCornerShape(20.dp)) {
            Text("Try asking yourself: What might this feeling be asking me to notice?", Modifier.padding(18.dp), color = Ink, fontSize = 15.sp)
        }
    }
}

@Composable
fun JournalScreen(value: String, onChange: (String) -> Unit, onSave: () -> Unit, notice: String) {
    Column(Modifier.fillMaxSize()) {
        Header("Let it take shape", "Your journal", "A private place to put thoughts into words.")
        Text("What’s taking up space in your mind today?", Modifier.padding(horizontal = 22.dp), color = Ink, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = value, onValueChange = onChange,
            modifier = Modifier.fillMaxWidth().weight(1f).padding(18.dp),
            placeholder = { Text("Start anywhere. A sentence, a list, or a feeling…") },
            shape = RoundedCornerShape(20.dp),
            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Teal, unfocusedBorderColor = Color(0xFFD8E2DC))
        )
        if (notice.isNotBlank()) Text(notice, Modifier.padding(horizontal = 22.dp), color = Teal, fontSize = 12.sp)
        Button(onClick = onSave, Modifier.fillMaxWidth().padding(horizontal = 18.dp).height(54.dp), shape = RoundedCornerShape(16.dp)) {
            Icon(Icons.Default.BookmarkAdd, null)
            Spacer(Modifier.width(8.dp))
            Text("Save reflection")
        }
        Text("Your journal stays on this device. It is not sent to the AI companion.", Modifier.padding(18.dp), color = Muted, fontSize = 11.sp)
    }
}

@Composable
fun CompanionScreen(chat: List<ChatLine>, message: String, onMessage: (String) -> Unit, busy: Boolean, onSend: (String) -> Unit) {
    val listState = rememberLazyListState()

    // Restore the conversation view at its newest message whenever chat opens
    // or a new message / typing indicator is added.
    LaunchedEffect(chat.size, busy) {
        if (chat.isNotEmpty()) {
            listState.animateScrollToItem(if (busy) chat.size else chat.lastIndex)
        }
    }

    Column(Modifier.fillMaxSize()) {
        Header("A supportive conversation", "Talk with Miora", "I can help you reflect, one step at a time.")
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(chat) { line ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = if (line.role == "user") Arrangement.End else Arrangement.Start) {
                    Surface(
                        color = if (line.role == "user") Mint else Color.White,
                        shape = RoundedCornerShape(18.dp),
                        modifier = Modifier.widthIn(max = 310.dp)
                    ) { Text(line.text, Modifier.padding(14.dp), color = Ink, fontSize = 15.sp) }
                }
            }
            if (busy) item { Text("Miora is thinking…", Modifier.padding(12.dp), color = Muted, fontSize = 13.sp) }
        }
        Row(Modifier.fillMaxWidth().background(Color.White).padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = message, onValueChange = onMessage, modifier = Modifier.weight(1f),
                placeholder = { Text("Share what’s on your mind…") },
                shape = RoundedCornerShape(18.dp), maxLines = 3
            )
            Spacer(Modifier.width(8.dp))
            IconButton(
                onClick = { if (message.isNotBlank() && !busy) onSend(message.trim()) },
                enabled = message.isNotBlank() && !busy
            ) { Icon(Icons.Default.Send, contentDescription = "Send", tint = Teal) }
        }
        Text("AI can make mistakes. For urgent or crisis support, contact local emergency or crisis services.", Modifier.padding(horizontal = 16.dp, vertical = 6.dp), color = Muted, fontSize = 10.sp)
    }
}

@Composable
fun SignInScreen(email: String, onEmail: (String) -> Unit, password: String, onPassword: (String) -> Unit, busy: Boolean, error: String, onSignIn: () -> Unit) {
    Column(Modifier.fillMaxSize().background(Cream).padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Miora", color = Ink, fontSize = 38.sp, fontWeight = FontWeight.Bold)
        Text("A little space for you.", color = Muted, fontSize = 16.sp)
        Spacer(Modifier.height(28.dp))
        Text("Sign in", color = Ink, fontSize = 24.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(14.dp))
        OutlinedTextField(value = email, onValueChange = onEmail, modifier = Modifier.fillMaxWidth(), label = { Text("Email") }, singleLine = true)
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(value = password, onValueChange = onPassword, modifier = Modifier.fillMaxWidth(), label = { Text("Password") }, singleLine = true)
        if (error.isNotBlank()) {
            Spacer(Modifier.height(10.dp))
            Text(error, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(18.dp))
        Button(onClick = onSignIn, enabled = email.isNotBlank() && password.isNotBlank() && !busy, modifier = Modifier.fillMaxWidth().height(52.dp)) {
            Text(if (busy) "Signing in…" else "Sign in")
        }
        Spacer(Modifier.height(12.dp))
        Text("Miora is invite-only. Ask your Miora administrator for an account.", color = Muted, fontSize = 12.sp)
    }
}


data class MioraProfile(val preferredName: String, val memorySummary: String)

private fun getMiora(path: String, token: String): Pair<Int, String> {
    val connection = (URL(BuildConfig.AI_BASE_URL + path).openConnection() as HttpURLConnection)
    connection.requestMethod = "GET"
    connection.connectTimeout = 15000
    connection.readTimeout = 20000
    connection.setRequestProperty("Authorization", "Bearer $token")
    val code = connection.responseCode
    val stream = if (code in 200..299) connection.inputStream else connection.errorStream
    val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
    connection.disconnect()
    return code to body
}

private fun putMiora(path: String, payload: JSONObject, token: String): Pair<Int, String> {
    val connection = (URL(BuildConfig.AI_BASE_URL + path).openConnection() as HttpURLConnection)
    connection.requestMethod = "PUT"
    connection.connectTimeout = 15000
    connection.readTimeout = 20000
    connection.doOutput = true
    connection.setRequestProperty("Content-Type", "application/json")
    connection.setRequestProperty("Authorization", "Bearer $token")
    connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
    val code = connection.responseCode
    val stream = if (code in 200..299) connection.inputStream else connection.errorStream
    val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
    connection.disconnect()
    return code to body
}

suspend fun loadMioraProfile(token: String): MioraProfile? = withContext(Dispatchers.IO) {
    try {
        val (code, body) = getMiora("profile", token)
        if (code !in 200..299) null else {
            val json = JSONObject(body)
            MioraProfile(json.optString("preferred_name"), json.optString("memory_summary"))
        }
    } catch (_: Exception) { null }
}

suspend fun saveMioraProfile(token: String, name: String, memory: String): Boolean = withContext(Dispatchers.IO) {
    try {
        val payload = JSONObject().put("preferred_name", name).put("memory_summary", memory)
        putMiora("profile", payload, token).first in 200..299
    } catch (_: Exception) { false }
}

suspend fun loadMioraHistory(token: String, conversationId: String): List<ChatLine>? = withContext(Dispatchers.IO) {
    if (conversationId.isBlank()) return@withContext null
    try {
        val (code, body) = getMiora("conversations/$conversationId/messages", token)
        if (code !in 200..299) null else {
            val json = JSONObject(body)
            val array = json.optJSONArray("messages") ?: JSONArray()
            val loaded = mutableListOf<ChatLine>()
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                val role = item.optString("role")
                val content = item.optString("content")
                if ((role == "user" || role == "assistant") && content.isNotBlank()) loaded.add(ChatLine(role, content))
            }
            loaded
        }
    } catch (_: Exception) { null }
}

@Composable
fun ProfileScreen(name: String, onName: (String) -> Unit, memory: String, onMemory: (String) -> Unit, onSave: () -> Unit, notice: String) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 18.dp)) {
        Header("Your information", "Profile & memory", "Choose what Miora can remember between conversations.")
        Text("What should Miora call you?", Modifier.padding(horizontal = 22.dp), color = Ink, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(value = name, onValueChange = onName, modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 8.dp), singleLine = true, placeholder = { Text("Your preferred name") })
        Text("Things you want Miora to remember", Modifier.padding(horizontal = 22.dp, vertical = 8.dp), color = Ink, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(value = memory, onValueChange = onMemory, modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp).padding(horizontal = 18.dp, vertical = 8.dp), placeholder = { Text("Add context, goals, preferences, or things you want to pick up next time…") })
        Text("Only save information you choose to share here. You can edit or erase it at any time. Your journal is separate and is never sent to Miora.", Modifier.padding(horizontal = 22.dp, vertical = 8.dp), color = Muted, fontSize = 12.sp)
        if (notice.isNotBlank()) Text(notice, Modifier.padding(horizontal = 22.dp, vertical = 8.dp), color = Teal, fontSize = 13.sp)
        Button(onClick = onSave, modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp).height(52.dp), shape = RoundedCornerShape(16.dp)) { Text("Save profile and memory") }
    }
}

data class MioraSession(val accessToken: String, val refreshToken: String)
data class MioraChatResult(val reply: String, val conversationId: String, val accessToken: String, val refreshToken: String)

private fun postMiora(path: String, payload: JSONObject, token: String = ""): Pair<Int, String> {
    val connection = (URL(BuildConfig.AI_BASE_URL + path).openConnection() as HttpURLConnection)
    connection.requestMethod = "POST"
    connection.connectTimeout = 15000
    connection.readTimeout = 45000
    connection.doOutput = true
    connection.setRequestProperty("Content-Type", "application/json")
    if (token.isNotBlank()) connection.setRequestProperty("Authorization", "Bearer $token")
    connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
    val code = connection.responseCode
    val stream = if (code in 200..299) connection.inputStream else connection.errorStream
    val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
    connection.disconnect()
    return code to body
}

suspend fun loginMiora(email: String, password: String): Triple<String?, String, String> {
    return try {
        val (code, body) = withContext(Dispatchers.IO) {
            postMiora("auth/login", JSONObject().put("email", email).put("password", password))
        }
        if (code in 200..299) {
            val json = JSONObject(body)
            Triple(json.optString("access_token"), "", json.optString("refresh_token"))
        } else Triple(null, "Sign-in failed. Check your email and password, then try again.", "")
    } catch (_: Exception) {
        Triple(null, "Could not reach Miora. Please try again.", "")
    }
}

private suspend fun refreshMioraSession(refreshToken: String): MioraSession? {
    if (refreshToken.isBlank()) return null
    return try {
        val (code, body) = withContext(Dispatchers.IO) {
            postMiora("auth/refresh", JSONObject().put("refresh_token", refreshToken))
        }
        if (code in 200..299) {
            val json = JSONObject(body)
            MioraSession(json.optString("access_token"), json.optString("refresh_token"))
        } else null
    } catch (_: Exception) { null }
}

suspend fun askMiora(text: String, history: List<ChatLine>, token: String, refreshToken: String, conversationId: String): MioraChatResult {
    var activeAccess = token
    var activeRefresh = refreshToken
    return try {
        suspend fun sendChat(): Pair<Int, String> = withContext(Dispatchers.IO) {
            val messages = JSONArray()
            history.takeLast(12).forEach { messages.put(JSONObject().put("role", it.role).put("content", it.text)) }
            val payload = JSONObject().put("messages", messages)
            if (conversationId.isNotBlank()) payload.put("conversation_id", conversationId)
            postMiora("chat", payload, activeAccess)
        }

        var (code, response) = sendChat()
        if (code == 401 || code == 403) {
            val refreshed = refreshMioraSession(activeRefresh)
            if (refreshed != null && refreshed.accessToken.isNotBlank()) {
                activeAccess = refreshed.accessToken
                activeRefresh = refreshed.refreshToken
                val retry = sendChat()
                code = retry.first
                response = retry.second
            }
        }
        if (code !in 200..299) {
            MioraChatResult("I’m having trouble connecting right now. Please sign in again if this continues.", conversationId, activeAccess, activeRefresh)
        } else {
            val json = JSONObject(response)
            MioraChatResult(
                json.optString("reply", "I’m here with you. Could you tell me a little more?"),
                json.optString("conversation_id", conversationId),
                activeAccess, activeRefresh
            )
        }
    } catch (_: Exception) {
        MioraChatResult("I can’t reach the AI service yet. Please try again in a moment.", conversationId, activeAccess, activeRefresh)
    }
}
