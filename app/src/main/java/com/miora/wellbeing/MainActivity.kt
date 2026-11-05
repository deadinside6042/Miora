package com.miora.wellbeing

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
    val scope = rememberCoroutineScope()

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
                        prefs.edit().putString("access_token", accessToken).apply()
                        conversationId = ""
                        prefs.edit().remove("conversation_id").apply()
                    } else authError = result.second
                    busy = false
                }
            }
        } else Scaffold(
            containerColor = Cream,
            bottomBar = {
                NavigationBar(containerColor = Color.White) {
                    listOf("Home", "Mood", "Journal", "Companion").forEach { item ->
                        NavigationBarItem(
                            selected = tab == item,
                            onClick = { tab = item },
                            icon = {
                                Icon(
                                    when(item) {
                                        "Home" -> Icons.Default.Home
                                        "Mood" -> Icons.Default.SentimentSatisfied
                                        "Journal" -> Icons.Default.EditNote
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
                    else -> CompanionScreen(chat, message, { message = it }, busy, { userText ->
                        chat = chat + ChatLine("user", userText)
                        message = ""
                        busy = true
                        scope.launch {
                            val result = withContext(Dispatchers.IO) { askMiora(userText, chat, accessToken, conversationId) }
                            chat = chat + ChatLine("assistant", result.first)
                            if (result.second.isNotBlank()) {
                                conversationId = result.second
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
    Column(Modifier.fillMaxSize()) {
        Header("A supportive conversation", "Talk with Miora", "I can help you reflect, one step at a time.")
        LazyColumn(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
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

suspend fun loginMiora(email: String, password: String): Pair<String?, String> {
    return try {
        val connection = (URL(BuildConfig.AI_BASE_URL + "auth/login").openConnection() as HttpURLConnection)
        connection.requestMethod = "POST"
        connection.connectTimeout = 15000
        connection.readTimeout = 20000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        val payload = JSONObject().put("email", email).put("password", password)
        connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val body = stream.bufferedReader().use { it.readText() }
        if (code in 200..299) JSONObject(body).optString("access_token") to ""
        else null to "Sign-in failed. Check your email and password, then try again."
    } catch (_: Exception) {
        null to "Could not reach Miora. Please try again."
    }
}

suspend fun askMiora(text: String, history: List<ChatLine>, token: String, conversationId: String): Pair<String, String> {
    return try {
        val connection = (URL(BuildConfig.AI_BASE_URL + "chat").openConnection() as HttpURLConnection)
        connection.requestMethod = "POST"
        connection.connectTimeout = 15000
        connection.readTimeout = 45000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        connection.setRequestProperty("Authorization", "Bearer $token")
        val messages = JSONArray()
        history.takeLast(12).forEach { messages.put(JSONObject().put("role", it.role).put("content", it.text)) }
        val payload = JSONObject().put("messages", messages)
        if (conversationId.isNotBlank()) payload.put("conversation_id", conversationId)
        connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
        val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
        val response = stream.bufferedReader().use { it.readText() }
        if (connection.responseCode !in 200..299) {
            "I’m having trouble connecting right now. Please try again in a moment." to conversationId
        } else {
            val json = JSONObject(response)
            json.optString("reply", "I’m here with you. Could you tell me a little more?") to json.optString("conversation_id", conversationId)
        }
    } catch (e: Exception) {
        "I can’t reach the AI service yet. Please try again in a moment." to conversationId
    }
}
