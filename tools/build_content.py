"""Source of truth for tips, milestones and registrations.
Run `python3 tools/build_content.py` to regenerate content.js (used by the app and by report/make_report.py)."""
import json, pathlib

BIRTH = "2026-10-12T04:24:00"  # local time (America/Toronto)
BABY, MOM, SURNAME = "Aveer", "Navjot", "Singh"

# Daily tips by day of life. 'today' = for today, 'next' = what's coming + parent preparedness.
# Days 1-14 individually, then weekly (by first day of week), then monthly. General guidance, not medical advice.
TIPS = [
 {"from": 1, "today": "Colostrum is small in volume but it's exactly what Aveer needs. Aim for at least 8 feeds in 24 hours and expect 1+ wet diaper and black, tarry meconium poop.",
  "next": "Days 2-3: many babies cluster-feed and are fussier at night (the 'second night'). Plan shifts so Navjot can sleep between feeds."},
 {"from": 2, "today": "Expect about 2+ wet diapers today. Frequent feeding now helps milk come in. Skin-to-skin calms babies and helps feeding.",
  "next": "Milk usually 'comes in' around days 2-5; breasts may feel full or engorged. Frequent feeds and cold compresses after feeds help."},
 {"from": 3, "today": "Expect about 3+ wet diapers. Watch for jaundice (yellow skin or eyes); it often peaks around days 3-5. Press gently on the skin of the chest in daylight to check.",
  "next": "Call the doctor promptly if yellow colour spreads to the belly or legs, or Aveer becomes very sleepy and hard to wake for feeds."},
 {"from": 4, "today": "Expect about 4+ wet diapers and poops changing from black to green to yellow. Losing some weight in the first days is normal.",
  "next": "From day 5, look for 6+ heavy wet diapers a day and regular yellow, seedy poops in breastfed babies. Fewer is a reason to call your provider."},
 {"from": 5, "today": "6+ wet diapers a day from now on is the sign of good intake. Breastfed babies usually also have 2-3+ yellow poops a day in the first weeks.",
  "next": "Health Canada recommends 400 IU of vitamin D drops daily for breastfed babies. Ask at the next visit if you haven't started."},
 {"from": 6, "today": "Always put Aveer to sleep on his back, in his own crib or bassinet, on a firm flat surface with no pillows, bumpers or toys. Room-sharing is recommended for the first 6 months.",
  "next": "Baby blues (tearfulness, mood swings) are common in the first 2 weeks. If low mood lasts longer or feels heavy, Navjot should talk to her provider."},
 {"from": 7, "today": "One week old. Many babies have a growth spurt around days 7-10: more frequent feeding is normal and helps supply.",
  "next": "Babies are usually back to birth weight by 10-14 days. Expect a weight check at the next doctor visit."},
 {"from": 8, "today": "Keep the umbilical cord stump clean and dry and fold the diaper below it. It usually falls off in 1-3 weeks.",
  "next": "Sponge baths are simplest until the cord stump falls off. Have a warm room, towel and clean diaper ready before you start."},
 {"from": 9, "today": "Start short tummy time while Aveer is awake and supervised: a few minutes, a few times a day, on your chest counts too.",
  "next": "Plan who handles night feeds and nappies this week so both parents get at least one longer stretch of sleep."},
 {"from": 10, "today": "Fever check: a rectal temperature of 38.0 C or higher in a baby under 3 months needs medical attention right away.",
  "next": "Keep a digital thermometer at home and save Health811 (dial 811) for nurse advice any time in Ontario."},
 {"from": 11, "today": "Trim or file nails when Aveer is drowsy; newborn nails are soft and grow fast. Scratch mitts help in between.",
  "next": "Around 2-3 weeks another growth spurt is common: expect a few days of cluster feeding."},
 {"from": 12, "today": "Hiccups, sneezes, noisy breathing and startles are all normal newborn behaviours.",
  "next": "Write down questions for the 2-week check-up: weight, feeding, vitamin D, sleep, jaundice."},
 {"from": 13, "today": "Talk, sing and make eye contact; newborns focus best on faces about 20-30 cm away.",
  "next": "If you're using bottles, pace the feed: hold the bottle more horizontal and let Aveer take breaks."},
 {"from": 14, "today": "Two weeks old. Most babies have regained their birth weight by now.",
  "next": "Weeks 3-6: crying often increases and peaks around 6-8 weeks. It's normal and it passes."},
 {"from": 15, "today": "Growth spurt weeks: more feeding and fussiness for a few days is normal. Follow Aveer's cues.",
  "next": "If crying gets overwhelming, it's OK to put Aveer down safely in the crib and step away for a few minutes. Never shake a baby."},
 {"from": 22, "today": "Help Aveer learn day vs night: bright, active days; dark, quiet, boring night feeds.",
  "next": "Book the 2-month check-up and vaccines if not already scheduled (Ontario's routine schedule starts at 2 months)."},
 {"from": 29, "today": "One month old. Lifting his head briefly during tummy time and staring at faces are common now.",
  "next": "Social smiles usually appear around 6 weeks. Smile and talk back; this is early conversation."},
 {"from": 36, "today": "Peak crying period (around 6-8 weeks) for many babies. Soothing ideas: holding, rocking, white noise, a walk.",
  "next": "Navjot's own 6-week postpartum check-up is important: physical recovery, mood, contraception, Synthroid levels."},
 {"from": 43, "today": "Six weeks. Look out for the first social smile!",
  "next": "2-month vaccines are coming. Bring the yellow immunization card; feeding or a cuddle right after helps."},
 {"from": 50, "today": "Aveer may be awake and alert for longer stretches. Offer high-contrast pictures and lots of face time.",
  "next": "Vaccine day tips: dress him in easy clothes, feed or cuddle during or after the shots, and expect some sleepiness after."},
 {"from": 57, "today": "Two months: social smiles, cooing and holding the head up during tummy time are typical.",
  "next": "Over the next weeks, Aveer will start bringing hands to mouth and swiping at toys. Offer safe, washable toys."},
 {"from": 64, "today": "Respond to coos with your own sounds: turn-taking builds language.",
  "next": "Start thinking about a consistent, simple bedtime routine (bath or wipe-down, feed, song, bed)."},
 {"from": 71, "today": "Keep tummy time going: aim for longer total time across the day as he gets stronger.",
  "next": "Rolling can start as early as 3-4 months. Never leave Aveer alone on a bed, sofa or change table."},
 {"from": 78, "today": "Babies often settle into more predictable feed and sleep patterns around 3 months.",
  "next": "4-month vaccines are next. Also plan ahead for the end of parental leave and childcare options if relevant."},
 {"from": 91, "today": "Three months: chuckles, head control and grabbing at objects are emerging.",
  "next": "Around 4 months, many babies have a temporary sleep change (the '4-month regression'). Consistent routines help."},
 {"from": 122, "today": "Four months: rolling, laughing and holding a toy are typical. 4-month vaccines are due.",
  "next": "Solid foods usually start around 6 months, with iron-rich foods first. Watch for readiness: sitting with support and interest in food."},
 {"from": 153, "today": "Five months: babbling and reaching for everything. Keep small objects out of reach.",
  "next": "Babyproof before he moves: outlet covers, secure furniture, and keep cords and small items out of reach."},
 {"from": 183, "today": "Six months: time for iron-rich first foods (meat, fish, iron-fortified cereal, beans) and 6-month vaccines.",
  "next": "Introduce common allergens (like peanut and egg) early and one at a time, unless your doctor advises otherwise."},
 {"from": 214, "today": "Seven months: sitting more steadily and passing toys hand to hand.",
  "next": "Teething can bring drooling and gum chewing. Clean gums and first teeth with a soft cloth or brush."},
 {"from": 244, "today": "Eight months: crawling or scooting may start. Get down on the floor and check for hazards.",
  "next": "Separation anxiety often appears around 9 months. Short, warm goodbyes help."},
 {"from": 275, "today": "Nine months: 'mamama' babbling, stranger shyness and sitting without support are typical.",
  "next": "Offer a cup with small sips of water and finger foods to practise self-feeding."},
 {"from": 305, "today": "Ten months: pulling to stand and cruising along furniture. Secure heavy furniture to walls.",
  "next": "Plan the 12-month check-up and vaccines."},
 {"from": 336, "today": "Eleven months: waving, pointing and understanding 'no'.",
  "next": "Around 9-12 months, whole (3.25%) cow's milk can be introduced in a cup (about 500-750 mL a day max), per Health Canada."},
 {"from": 366, "today": "Happy first birthday, Aveer! 12-month vaccines are due.",
  "next": "Next: first steps, first words and lots of exploring. Keep reading together every day."},
]

# Typical minimum wet diapers by day of life (common Canadian breastfeeding guidance).
WET_MIN = {1: 1, 2: 2, 3: 3, 4: 4}  # day 5+ -> 6
FEEDS_MIN = 8

MILESTONES = [
 {"band": "Firsts", "months": 0, "learn": "Special moments worth remembering.", "items": [
   ["first_feed", "First feed"], ["first_bath", "First bath"], ["first_home", "First day home"],
   ["first_visit", "First doctor visit"], ["cord_off", "Umbilical cord stump fell off"],
   ["birth_weight", "Back to birth weight"], ["first_outing", "First outing"],
   ["first_smile", "First social smile"], ["first_laugh", "First laugh"], ["first_roll", "First roll over"],
   ["first_tooth", "First tooth"], ["first_food", "First solid food"], ["first_word", "First word"], ["first_steps", "First steps"]]},
 {"band": "1 month", "months": 1, "learn": "Newborns see best at 20-30 cm and recognise your voice. Talk, sing and hold him close.", "items": [
   ["m1_head", "Lifts head briefly during tummy time"], ["m1_faces", "Focuses on faces"], ["m1_sound", "Startles or reacts to loud sounds"], ["m1_calm", "Calms when picked up or spoken to"]]},
 {"band": "2 months", "months": 2, "learn": "Social smiles and cooing begin. Respond to sounds and smiles to build connection.", "items": [
   ["m2_smile", "Smiles when you talk to him"], ["m2_coo", "Makes sounds other than crying"], ["m2_watch", "Watches you as you move"], ["m2_head", "Holds head up during tummy time"], ["m2_hands", "Opens hands briefly"]]},
 {"band": "4 months", "months": 4, "learn": "Head control, chuckles and reaching for toys. Give lots of floor and tummy time.", "items": [
   ["m4_chuckle", "Chuckles"], ["m4_steady", "Holds head steady without support"], ["m4_toy", "Holds a toy put in his hand"], ["m4_mouth", "Brings hands to mouth"], ["m4_elbows", "Pushes up onto elbows on tummy"], ["m4_turn", "Turns head toward your voice"]]},
 {"band": "6 months", "months": 6, "learn": "Laughing, babbling and rolling. Starting solids around now.", "items": [
   ["m6_laugh", "Laughs"], ["m6_raspberry", "Blows raspberries / squeals"], ["m6_roll", "Rolls from tummy to back"], ["m6_reach", "Reaches to grab a toy"], ["m6_sit", "Leans on hands to support himself sitting"], ["m6_mirror", "Likes looking at himself in a mirror"]]},
 {"band": "9 months", "months": 9, "learn": "Sitting alone, babbling 'mamama' and some stranger shyness are typical.", "items": [
   ["m9_sit", "Sits without support"], ["m9_babble", "Babbles 'mamama' / 'bababa'"], ["m9_arms", "Lifts arms to be picked up"], ["m9_hands", "Moves things from one hand to the other"], ["m9_look", "Looks for things he drops"], ["m9_shy", "Shy or clingy with strangers"]]},
 {"band": "12 months", "months": 12, "learn": "Pulling to stand, waving and first words.", "items": [
   ["m12_wave", "Waves bye-bye"], ["m12_mama", "Calls a parent 'mama' or 'dada'"], ["m12_stand", "Pulls up to stand"], ["m12_cruise", "Walks holding on to furniture"], ["m12_pincer", "Picks things up between thumb and finger"], ["m12_no", "Understands 'no'"]]},
]
MILESTONE_NOTE = "Every baby develops at his own pace; these are typical ages, not deadlines. Mention any worries at check-ups."

# Ontario registrations for a baby born in Ontario to permanent-resident parents.
# due_days = days after birth (null = no fixed deadline).
REGS = [
 {"key": "nrs", "group": "Required", "title": "Register the birth (5-in-1 newborn bundle)", "due_days": 30,
  "what": "Legally required within 30 days. Free within 12 months. The online bundle also orders the birth certificate, SIN and Canada Child Benefit.",
  "link": "https://www.ontario.ca/page/register-birth-new-baby"},
 {"key": "birth_cert", "group": "Required", "title": "Birth certificate received", "due_days": None,
  "what": "Ordered in the bundle; usually issued within about 15 business days after the birth is registered. Aveer is a Canadian citizen by birth in Canada; the birth certificate is his proof.",
  "link": "https://www.ontario.ca/page/get-or-replace-ontario-birth-certificate"},
 {"key": "ohip", "group": "Required", "title": "OHIP health card received", "due_days": 56,
  "what": "The hospital submits the Ontario Health Coverage Infant Registration form. Keep the bottom part (it shows his health number). Card arrives within about 8 weeks; contact ServiceOntario if not.",
  "link": "https://www.ontario.ca/page/apply-ohip-and-get-health-card"},
 {"key": "sin", "group": "Required", "title": "Social Insurance Number (SIN) received", "due_days": None,
  "what": "Applied for through the bundle; mailed after the birth is registered. Needed for RESP grants and the Canada Learning Bond.",
  "link": "https://www.canada.ca/en/employment-social-development/services/sin.html"},
 {"key": "ccb", "group": "Required", "title": "Canada Child Benefit (incl. Ontario Child Benefit) started", "due_days": None,
  "what": "Applied through the bundle by the primary caregiver (PR status qualifies). Check status in CRA My Account. Don't apply a second way.",
  "link": "https://www.canada.ca/en/revenue-agency/services/child-family-benefits/canada-child-benefit-overview.html"},
 {"key": "benefits", "group": "Required", "title": "Add Aveer to employer health/dental benefits", "due_days": 30,
  "what": "Most group plans require adding a newborn within about 30-31 days of birth. Check each parent's plan.",
  "link": None},
 {"key": "ei", "group": "Required", "title": "EI maternity / parental benefits applied", "due_days": 28,
  "what": "Apply as soon as you stop working; delaying more than 4 weeks can mean losing benefits. Record of Employment comes from the employer.",
  "link": "https://www.canada.ca/en/services/benefits/ei/ei-maternity-parental.html"},
 {"key": "doctor", "group": "Required", "title": "Family doctor / pediatrician follow-up booked", "due_days": 3,
  "what": "First check is usually within a few days of going home, then around 2 weeks, 2, 4, 6, 9, 12 months.",
  "link": None},
 {"key": "screening", "group": "Recommended", "title": "Newborn screening and hearing screening done", "due_days": 7,
  "what": "Blood-spot screening is done in the first days; the infant hearing screen is usually done in hospital. Ask if either was missed.",
  "link": "https://www.newbornscreening.on.ca"},
 {"key": "immunization", "group": "Recommended", "title": "Immunization record (yellow card) ready", "due_days": 60,
  "what": "Routine Ontario vaccines start at 2 months. Bring the card to every vaccine visit.",
  "link": None},
 {"key": "resp", "group": "Recommended", "title": "Open an RESP (Canada Education Savings Grant)", "due_days": None,
  "what": "The government adds 20% on contributions (CESG); the Canada Learning Bond may apply depending on income. Needs Aveer's SIN.",
  "link": "https://www.canada.ca/en/services/benefits/education/education-savings.html"},
 {"key": "passport", "group": "Recommended", "title": "Canadian passport for Aveer", "due_days": None,
  "what": "Needed before any international travel. Requires the birth certificate and photos.",
  "link": "https://www.canada.ca/en/immigration-refugees-citizenship/services/canadian-passports/child-passport.html"},
 {"key": "will", "group": "Recommended", "title": "Update wills and name a guardian", "due_days": None,
  "what": "Name a guardian for Aveer and update beneficiaries on insurance, RRSP/TFSA and pension plans.", "link": None},
 {"key": "insurance", "group": "Good to have", "title": "Review life and disability insurance", "due_days": None,
  "what": "A new dependant often changes how much coverage you need.", "link": None},
 {"key": "carseat", "group": "Good to have", "title": "Register the car seat with the manufacturer", "due_days": None,
  "what": "So you're notified of recalls. The registration card is in the box or online.", "link": None},
 {"key": "citizenship", "group": "Good to have", "title": "Parents' citizenship application: keep IRCC updated", "due_days": None,
  "what": "Aveer is already Canadian by birth. Keep your own application details (address, etc.) current with IRCC.", "link": None},
]

content = {"birth": BIRTH, "baby": BABY, "mom": MOM, "surname": SURNAME, "tips": TIPS,
           "wetMin": WET_MIN, "feedsMin": FEEDS_MIN, "milestones": MILESTONES,
           "milestoneNote": MILESTONE_NOTE, "regs": REGS}
out = pathlib.Path(__file__).resolve().parent.parent / "content.js"
out.write_text("window.CONTENT = " + json.dumps(content, ensure_ascii=False, indent=1) + ";\n")
print("wrote", out, out.stat().st_size, "bytes")
