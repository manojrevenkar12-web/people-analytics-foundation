"""What people write: exit-survey comments and questions to the People team. The reason and the right answer stay
here (in `Keys`), out of the platform's reach.
"""

from __future__ import annotations

from datetime import timedelta

from paf.world import luck
from paf.world.company import Company, month_end, month_start
from paf.world.systems import Exports, Keys

REASONS = {
    "pay": (
        [
            "The salary was below what I was offered elsewhere.",
            "I could not make the numbers work on my current pay.",
            "Compensation did not keep up with the market for my skills.",
        ],
        [
            "An offer came in at a quarter more and I could not say no.",
            "Money, honestly. The new place simply pays more.",
        ],
    ),
    "manager": (
        [
            "I did not get along with my manager.",
            "My lead rarely gave feedback and decisions felt arbitrary.",
            "After the change of team lead things went downhill for me.",
        ],
        [
            "The person I reported to and I never found a way to work together.",
            "Leadership in my team was the deciding factor.",
        ],
    ),
    "career_growth": (
        ["I saw no path to the next level here.", "I was ready for more responsibility but no promotion was in sight."],
        ["I outgrew the role and nothing bigger opened up.", "Three years at the same level was enough."],
    ),
    "workload": (
        ["The overtime before deliveries was too much.", "I was worn out by the weekend shifts."],
        ["The pace in the last quarter of every year is not sustainable.", "I never got my evenings back."],
    ),
    "role_fit": (
        [
            "The job turned out to be different from what the interview described.",
            "I never really settled into the role.",
        ],
        ["What I do every day is not what I signed up for.", "It was not the right fit from the first weeks."],
    ),
    "relocation": (
        ["My partner got a job in another city.", "I am moving back to my home country."],
        ["Family reasons take me to the north.", "We are relocating for my partner's work."],
    ),
    "culture": (
        ["I did not feel I belonged here.", "The atmosphere changed a lot as the company grew."],
        ["It stopped feeling like my kind of place.", "Too many processes for my taste now."],
    ),
}
PRAISE = {
    "pay": "The pay itself was fair, to be clear.",
    "manager": "My manager was great and supportive.",
    "career_growth": "I learned a lot and grew here.",
    "workload": "The workload was fine most of the time.",
    "culture": "I liked my colleagues a lot.",
    "role_fit": "The work itself was interesting.",
}
NEUTRAL = ["Thanks for the time here.", "All the best to the team.", "Happy to talk more if useful."]

# (category, routine phrasings, new phrasings, answer: passage id or "person")
QUESTIONS = [
    (
        "vacation",
        ["How many vacation days do I have per year?", "Does my vacation entitlement go up with tenure?"],
        ["Am I right that I get more holiday the longer I stay?"],
        "P-VAC",
    ),
    (
        "payday",
        ["When is salary paid each month?", "Which day does the salary arrive?"],
        ["When should I expect money in my account?"],
        "P-PAY",
    ),
    (
        "pension",
        ["Does the company add to the company pension?", "How much does the employer pay into the pension?"],
        ["Is there a top-up on the retirement plan?"],
        "P-PEN",
    ),
    (
        "relocation",
        ["What does relocation support cover?", "Is there a budget for moving from abroad?"],
        ["Will you pay for my move from Kyiv?"],
        "P-REL",
    ),
    (
        "benefits",
        ["How large is the flexible benefits budget?", "What can I spend the benefits budget on?"],
        ["Is there a monthly perk allowance?"],
        "P-BEN",
    ),
    (
        "learning",
        ["Is there a learning budget?", "Can I book a course on the learning budget?"],
        ["Who pays for a certification I want to take?"],
        "P-LRN",
    ),
    (
        "parental",
        ["When do I tell you about parental leave?", "How early must parental leave be announced?"],
        ["We are expecting a baby, what is the notice period for leave?"],
        "P-PAR",
    ),
    (
        "sick",
        ["Do I need a doctor's note when I am ill?", "From which day is a sick note needed?"],
        ["I have the flu, what paperwork do you need?"],
        "P-SIC",
    ),
    (
        "pay_dispute",
        ["My salary is lower than a colleague doing the same job.", "I think my last raise was wrong."],
        ["I found out the new hire earns more than me."],
        "person",
    ),
    (
        "conflict",
        ["I have a serious conflict with my manager.", "Someone in my team is treating me badly."],
        ["I do not feel safe raising things in my team."],
        "person",
    ),
    (
        "clearance",
        ["What is the status of my security clearance?", "My clearance has been pending for weeks."],
        ["Has my vetting come back yet?"],
        "person",
    ),
]
ROUTINE_HEAVY = {"vacation", "payday", "benefits", "pension", "relocation"}


def write(company: Company, w: dict, world_name: str, seed: int, x: Exports, k: Keys) -> None:
    new_share = float(w[world_name].get("new_phrasing_share", 0.0))
    es = w["exit_survey"]
    # exit survey: voluntary leavers who answer
    n = 0
    for e in sorted(company.jobs.values(), key=lambda j: j.eid):
        if e.exit_kind != "voluntary" or e.exit is None or e.exit > month_end(company.start, company.months - 1):
            continue
        if e.exit < company.start or luck.uniform(seed, "respond", e.eid) >= es["response_rate"]:
            continue
        reason = e.reason or "culture"
        base, new = REASONS[reason]
        pool = new if luck.uniform(seed, "exitnew", e.eid) < new_share else base
        parts = [luck.choice(seed, pool, "exittext", e.eid)]
        if luck.uniform(seed, "praise", e.eid) < es["distractor_rate"]:
            other = [t for t in PRAISE if t != reason]
            parts.insert(
                int(luck.uniform(seed, "praisepos", e.eid) * 2), PRAISE[luck.choice(seed, other, "praisewho", e.eid)]
            )
        parts.append(luck.choice(seed, NEUTRAL, "neutral", e.eid))
        n += 1
        rid = f"S-{n:04d}"
        x.exit_survey.append(
            {
                "response_id": rid,
                "submitted": (e.exit - timedelta(days=3)).isoformat(),
                "org_unit": e.team_on(e.exit),
                "text": " ".join(parts),
            }
        )
        k.survey_truth[rid] = reason

    # helpdesk: questions to the People team, from everyone employed
    hd = w["helpdesk"]
    t = 0
    for m in range(company.months):
        ms, me = month_start(company.start, m), month_end(company.start, m)
        staff = [e for e in company.jobs.values() if e.active_on(me) and e.kind != "contractor"]
        wave = m in hd["onboarding_wave_months"]
        count = int(len(staff) * hd["tickets_per_100_people_month"] / 100 * (1.5 if wave else 1.0))
        for i in range(count):
            t += 1
            e = staff[int(luck.uniform(seed, "asker", m, i) * len(staff))]
            cats = QUESTIONS
            if wave and luck.uniform(seed, "wavecat", m, i) < 0.6:
                cats = [q for q in QUESTIONS if q[0] in ROUTINE_HEAVY]
            cat, base, new, answer = cats[int(luck.uniform(seed, "cat", m, i) * len(cats))]
            pool = new if luck.uniform(seed, "qnew", m, i) < new_share else base
            text = luck.choice(seed, pool, "qtext", m, i)
            tid = f"T-{t:05d}"
            sid = k.new_id.get(e.eid) if ms >= month_start(company.start, company.cutover) else None
            sid = sid or (str(k.old_nr[e.eid]) if e.eid in k.old_nr else k.new_id.get(e.eid, "?"))
            created = ms + timedelta(days=int(luck.uniform(seed, "qday", m, i) * (me - ms).days))
            x.tickets.append({"ticket_id": tid, "requester": sid, "created_at": created.isoformat(), "text": text})
            # the People team answering by hand (the world's behaviour): hours to answer, minutes spent, mistakes
            hours = 6.0 * (2.0 ** (2.2 * luck.uniform(seed, "mh", tid))) * (1.5 if wave else 1.0)
            k.ticket_truth[tid] = {
                "category": cat,
                "answer": answer,
                "sensitive": answer == "person",
                "manual_hours": round(hours, 2),
                "manual_minutes": 22.0 if answer == "person" else 9.0,
                "manual_wrong": luck.uniform(seed, "mwrong", tid) < 0.03,
                "month": m,
                "requester_eid": e.eid,
            }
