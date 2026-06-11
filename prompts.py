def brief_description_prompt(battalion, coy, incident_type, name, date, raw_dump):
    return f"""You are writing Section 6 (Brief Description) of a Singapore Armed Forces (SAF) incident report.
The user typed in shorthand, point form, or spoken English. Extract every detail and rewrite correctly.

FORMATTING RULES — ABSOLUTE. ZERO EXCEPTIONS.

PARAGRAPH OPENINGS:
- Number every paragraph: 1. 2. 3. etc.
- FIRST paragraph MUST start: "On {date} at [HHMM]H,"
  CORRECT: "On 120526 at 1816H, 3SG SEAN..."
- SAME-DAY subsequent paragraphs start: "At [HHMM]H,"
  CORRECT: "At 2038H, serviceman reported..."
- NEW DATE paragraphs start: "On [DDMMYY] at [HHMM]H,"

DATE FORMAT — CRITICAL:
- ALWAYS DDMMYY. Six digits. No spaces. No slashes. No month names.
- CORRECT: 010626   WRONG: 1st June   WRONG: June 1   WRONG: 01/06/26
- If user says "1st June" convert to 010626. "12 May 26" → 120526.

TIME FORMAT:
- ALWAYS HHMM followed by letter H.
- CORRECT: 1816H, 0930H, 2038H   WRONG: 18:16   WRONG: 1816hrs

NUMBERS — CRITICAL:
- ALWAYS digits. NEVER words.
- CORRECT: "3 days MC"   WRONG: "three days MC"

RANKS AND NAMES:
- ALL ranks in CAPS: PTE LCP CPL 3SG 2SG SGT SSG MSG 3WO 2WO WO 2LT LTA CPT MAJ LTC COL
- ALL names in CAPS
- After first full name mention, use "serviceman"

MEDICAL FACILITIES — full name (ABBREV) on first mention, then abbrev only:
- SMC = Stagmont Medical Centre (SMC)
- KRHH = Kranji Regional Health Hub (KRHH)
- NTFGH = Ng Teng Fong General Hospital (NTFGH)
- SGH = Singapore General Hospital (SGH)
- TTSH = Tan Tock Seng Hospital (TTSH)
- NUH = National University Hospital (NUH)
- WHC = Woodlands Health Campus (WHC)
- IMH = Institute of Mental Health (IMH)
- SKH = Sengkang General Hospital (SKH)
- CGH = Changi General Hospital (CGH)
- NCC = National Cancer Centre (NCC)

SAF AMBULANCE: "SAF Ambulance (MID [number])" when MID given.
ESCORT: "He/She is accompanied by [RANK] [FULL NAME]."
MC: "[X] days MC from [DDMMYY] to [DDMMYY] (inclusive)."
HL: "[X] days hospitalisation leave from [DDMMYY] to [DDMMYY] (inclusive)."

SHORTHAND TO EXPAND:
RSO = report sick outside | RSI = report sick inside | MO = Medical Officer
amb = SAF Ambulance | escort/acc = accompanied by
MC = medical certificate leave | HL = hospitalisation leave | LD = light duty
d = days (e.g. "3d mc" = 3 days MC) | temp = temperature | diag = diagnosed
dept/dep = departed | arr = arrived | crit = critical areas | bcu = BCU
iv/drip = IV drip | voc = vehicle operator course | pc = platoon commander

INCOMPLETE TRANSCRIPT WARNING:
If the input appears to be cut off mid-sentence or key details seem missing (e.g. a sentence ends abruptly), add this line at the very end:
⚠️ Transcript may be incomplete — verify details before confirming.

INPUT:
Incident Type: {incident_type}
Serviceman: {name}
Date: {date}
Unit: {battalion}, {coy}

USER INPUT:
{raw_dump}

OUTPUT: numbered paragraphs only. No preamble. No explanation. Nothing else."""


def update_brief_prompt(existing_brief, raw_update):
    return f"""You are updating the Brief Description of a Singapore Armed Forces incident report.

EXISTING PARAGRAPHS (reproduce WORD FOR WORD — do NOT change anything):
{existing_brief}

NEW UPDATE (may be shorthand or spoken English):
{raw_update}

RULES:
1. Copy ALL existing paragraphs exactly unchanged — not a single character changed.
2. Append new numbered paragraphs continuing the sequence.
3. Wrap ONLY new paragraphs: <NEW>paragraph text here</NEW>
4. Return the COMPLETE updated Brief Description.

NEW PARAGRAPHS FORMAT:
- Same-day: "At [HHMM]H,"
- New date: "On [DDMMYY] at [HHMM]H,"
- Dates ALWAYS DDMMYY | Times ALWAYS HHMMH | Numbers always digits
- Ranks and names in CAPS
- Expand medical facility abbreviations on first new mention
- MC: "[X] days MC from [DDMMYY] to [DDMMYY] (inclusive)."

If the update appears incomplete add: ⚠️ Transcript may be incomplete — verify before confirming.

OUTPUT: complete numbered paragraphs only. No preamble."""


def medevac_nature_prompt(nature, avpu):
    return f"""For a Singapore Armed Forces 1733 MEDEVAC call, rewrite the nature of incident as ONE natural spoken sentence for reading aloud on the phone. Plain English. Return ONLY the sentence.
Nature: {nature} | AVPU: {avpu}"""


def safety_insights_prompt(incident_summaries, battalion, week_label):
    return f"""You are a safety officer for the Singapore Armed Forces.
Analyse the following incident reports from {battalion} for {week_label} and write a concise weekly safety insights report.

Format:
1. Summary (total incidents, breakdown by type)
2. Key Observations (2-3 patterns or concerning trends)
3. Recommendations (2-3 specific, actionable steps)
4. Open Cases (count and which need urgent updates)

Be direct and practical. Use military tone. Keep it under 300 words.
No preamble.

INCIDENT DATA:
{incident_summaries}"""
