-- Miora curated evidence pack v1
-- Run in Supabase SQL Editor after the knowledge_resources table exists.
-- These are original structured study notes, not copied source chapters.
-- Each record points to its authoritative source and describes scope/limitations.

insert into public.knowledge_resources
(title, source_name, source_url, resource_type, topic_tags, content, reviewed_at, review_status)
values
(
  'Doing What Matters in Times of Stress: practical skills map',
  'World Health Organization',
  'https://www.who.int/publications/i/item/9789240003927',
  'Evidence-informed self-help guide',
  array['stress','grounding','avoidance','rumination','acceptance','values','self-compassion','distress'],
  'STUDY NOTES — WHO guide for coping with adversity; evidence-informed and field-tested. It teaches a set of repeatable skills: (1) Grounding: deliberately orient attention to the body and immediate surroundings when pulled into distress; use sight, sound, touch and contact with the floor, without insisting the person must feel calm. (2) Notice and name: recognize thoughts and feelings as experiences occurring in the mind/body, rather than automatically treating every thought as a fact or command. (3) Unhooking: notice an unkind or repetitive thought, label it as a thought, and gently return attention to the current activity; do not argue endlessly with it. (4) Making room: allow difficult feelings to be present while choosing a safe, useful action, rather than waiting for discomfort to disappear first. (5) Values-guided action: identify what matters in the situation (for example care, responsibility, health, connection) and choose one small behaviour that expresses it. (6) Kindness: use a less punitive response toward oneself during difficulty. APPLICATION: offer one skill at a time, explain the purpose, ask permission, and adapt if focusing on the body or thoughts increases distress. Do not promise symptom relief or present these brief skills as a substitute for needed clinical care. Source provides a full 132-page illustrated guide and accompanying audio exercises.',
  now(),
  'approved'
),
(
  'NICE NG222: behavioural activation and activity-mood patterns',
  'National Institute for Health and Care Excellence',
  'https://www.nice.org.uk/guidance/ng222/chapter/recommendations',
  'Clinical guideline study notes',
  array['behavioural activation','depression','avoidance','procrastination','activity','mood','routine','withdrawal'],
  'STUDY NOTES — NICE NG222 describes behavioural activation as a structured psychological intervention. Its central working idea is to identify links between activities and mood, notice patterns of avoidance or withdrawal, and plan practical changes that increase engagement in meaningful or potentially rewarding activity. It is goal-oriented and focuses on current difficulties. PRACTICAL COACHING ADAPTATION: collaboratively map a recent day or week; identify what the person has stopped doing or is avoiding; notice what happens before and after the behaviour without blame; select one small, specific, realistic activity; decide when and where it will happen; then review what they noticed, not just whether they completed it perfectly. For overwhelming chores, scale the action down (for example, clear one surface for five minutes) and define a stopping point. IMPORTANT LIMIT: NICE describes formal behavioural activation as a structured intervention delivered by a practitioner with therapy-specific training and competence. Miora may explain basic principles and support low-risk planning, but must not claim to deliver a full clinical treatment or infer a diagnosis. NICE also describes guided self-help as structured CBT, behavioural activation, problem-solving or psychoeducation with practitioner support, usually over 6–8 sessions.',
  now(),
  'approved'
),
(
  'NICE NG222: structured problem-solving principles',
  'National Institute for Health and Care Excellence',
  'https://www.nice.org.uk/guidance/ng222/chapter/recommendations',
  'Clinical guideline study notes',
  array['problem-solving','overwhelm','decision-making','stress','planning','CBT','coping'],
  'STUDY NOTES — NICE NG222 describes problem-solving as a structured, goal-oriented approach focused on current problems. Core sequence: (1) define one problem clearly and specifically; (2) generate several possible solutions before judging them; (3) compare options for feasibility, likely benefits and costs; (4) choose one option; (5) make a concrete action plan; (6) review whether it helped and revise if needed. APPLICATION FOR OVERWHELM: when the person says everything is wrong, do not insist they pick the single biggest issue immediately. First externalize the demands into a short list. Separate items that are time-sensitive or safety-critical from those that can wait. Select one manageable next action and identify what can be postponed, delegated or simplified. Keep the plan collaborative and realistic; do not turn it into another demanding productivity standard. Ask one focused question only if needed to make the next step safe or feasible. LIMIT: the guideline describes formal interventions and treatment options in a clinical context; this conversational adaptation is educational support, not a complete treatment protocol.',
  now(),
  'approved'
),
(
  'WHO 2026: individually delivered psychological self-help interventions',
  'World Health Organization',
  'https://www.who.int/publications/i/item/9789240120785',
  'Implementation manual',
  array['guided self-help','psychological self-help','digital mental health','structured intervention','evidence','support'],
  'SOURCE SUMMARY — WHO publication dated 1 June 2026 describes individually delivered psychological self-help as an evidence-based and scalable approach using structured techniques and exercises for psychological distress and related symptoms. It covers guided and unguided delivery and provides implementation guidance for WHO Step-by-Step and Doing What Matters in Times of Stress. WHO reports that these interventions have demonstrated effectiveness in multiple randomized controlled trials. DESIGN IMPLICATIONS FOR MIORA: use structured, named skill pathways rather than improvised advice; present short exercises in a sequence; support practice and reflection; make clear whether an activity is unguided educational self-help or would ordinarily require a trained facilitator; track user feedback with consent; and avoid claiming that evidence for a specific WHO programme automatically proves the effectiveness of Miora itself. The full manual should be consulted before reproducing programme protocols.',
  now(),
  'approved'
)
on conflict do nothing;
