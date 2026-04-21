"""
Demo seed — creates a demo practitioner account with one fully loaded patient
(Shuva Mukhopadhyay) including care plan, supplements, recipes, 21 days of
check-in history, and a scheduled follow-up.

Run from backend/: python scripts/seed_demo.py
"""
import asyncio
import random
import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt as _bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload

from app.core.config import settings
from app.core.database import Base
from app.models.practitioner import Practitioner, SubscriptionTier
from app.models.patient import Patient, HealthProfile
from app.models.checkin import CheckInToken, DailyCheckIn
from app.models.plan import ConsultationPlan, Supplement, PlanSupplement, Recipe, PlanRecipe
from app.models.followup import FollowUp
from app.models.dosha_assessment import DoshaAssessment
from app.models.yoga import YogaAsana, VideoReference, PlanYogaAsana

_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
DATABASE_URL = _db_url
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

def hash_password(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()

DEMO_EMAIL    = "demo@dhanvantari.app"
DEMO_PASSWORD = "demo1234"


# ── Supplement data for Shuva's plan ────────────────────────────────────────

SHUVA_SUPPLEMENTS = [
    {
        "name": "Avipattikar Churna",
        "name_sanskrit": "Avipattikar Churna (Dhootpapeshwar)",
        "category": "Digestive",
        "purpose": "Supports digestion, reduces acid reflux and gut inflammation. Classical formula for Pitta in the digestive tract.",
        "dosha_effect": "Reduces Pitta, balances Kapha",
        "typical_dose": "½ tsp twice daily with water before meals",
        "cautions": "Avoid in excess during pregnancy. Monitor for loose stools in high doses.",
        "is_classical": True,
    },
    {
        "name": "Haridrakhandam",
        "name_sanskrit": "Haridrakhandam (Kottakkal)",
        "category": "Anti-inflammatory",
        "purpose": "Anti-inflammatory, supports respiratory and skin health, reduces allergic load. Turmeric-based classical formula.",
        "dosha_effect": "Reduces Kapha and Pitta, mildly increases Vata",
        "typical_dose": "¼ tsp twice daily with water after meals",
        "cautions": "Avoid in high Vata without ghee or milk. Not recommended in high doses during pregnancy.",
        "is_classical": True,
    },
    {
        "name": "Vyoshadi Vatkam",
        "name_sanskrit": "Vyoshadi Vatkam (Kottakkal)",
        "category": "Respiratory",
        "purpose": "Supports respiratory tract and digestion. Classical Kerala tablet for Kapha in the lungs, sinus congestion, and breathing difficulty.",
        "dosha_effect": "Reduces Kapha and Vata in respiratory tract",
        "typical_dose": "¼ tsp (or 2 tablets) twice daily with water after meals",
        "cautions": "Use cautiously in high Pitta conditions. Contains pippali (long pepper).",
        "is_classical": True,
    },
    {
        "name": "Neeri Tablets",
        "name_sanskrit": "Neeri (Aimil Pharmaceuticals)",
        "category": "Urinary",
        "purpose": "Urinary tract support — reduces UTI frequency, supports bladder health and kidney function. Contains Gokshura, Punarnava, Varuna.",
        "dosha_effect": "Reduces Vata and Pitta in urinary tract",
        "typical_dose": "1 tablet twice daily with water after meals",
        "cautions": "Generally safe. Consult if on diuretic medications.",
        "is_classical": False,
    },
]

SHUVA_RECIPES = [
    {
        "name": "Warm Oat Bowl (Shuva's Breakfast)",
        "meal_type": "Breakfast",
        "dosha_good_for": "Vata, Pitta",
        "dosha_avoid": "Kapha (reduce milk/sweetener)",
        "ingredients": "½ cup oats, 1 cup water or milk, chopped figs, 1 date, 6–8 almonds, 1 Brazil nut",
        "instructions": "Add oats and water (or milk) to a saucepan. Cook on low heat for 5–7 minutes. Add chopped figs, date pieces, almonds, and Brazil nuts. Serve warm.",
        "notes": "Provides steady energy and supports digestion. The nuts add healthy fat and Ojas. Best eaten within 1 hour of waking.",
        "is_tea": False,
    },
    {
        "name": "Savory Vegetable Oats",
        "meal_type": "Breakfast",
        "dosha_good_for": "Vata, Kapha",
        "dosha_avoid": None,
        "ingredients": "½ cup oats, 1 cup water, chopped carrots, zucchini or spinach, pinch turmeric, pinch cumin, salt to taste",
        "instructions": "Heat pan with a little oil or ghee. Add cumin and turmeric. Add chopped vegetables and sauté lightly. Add oats and water. Cook until soft (5–6 minutes).",
        "notes": "Savory breakfast alternative — good for those who prefer less sweet food in the morning. Lighter than the sweet oat bowl.",
        "is_tea": False,
    },
    {
        "name": "Barley Vegetable Bowl",
        "meal_type": "Lunch",
        "dosha_good_for": "Kapha, Pitta",
        "dosha_avoid": "High Vata (add more ghee)",
        "ingredients": "½ cup barley, carrots, green beans, zucchini, turmeric, cumin, ginger, salt",
        "instructions": "Cook barley in water until soft. In a separate pan, sauté cumin and ginger. Add chopped vegetables and cook until soft. Mix cooked barley and vegetables together. Add salt and turmeric. Serve warm.",
        "notes": "Barley is the recommended grain for Shuva — lighter than rice, reduces Kapha, supports urinary tract health. Best as main meal.",
        "is_tea": False,
    },
    {
        "name": "Light Chicken Vegetable Soup",
        "meal_type": "Lunch",
        "dosha_good_for": "Vata, Kapha",
        "dosha_avoid": None,
        "ingredients": "Chicken pieces (marinated), carrots, zucchini, ginger, turmeric, cumin, salt, water",
        "instructions": "Marinate chicken with spices beforehand. Add chicken and vegetables to pot. Add water, ginger, cumin, and turmeric. Simmer for 20–25 minutes. Serve warm.",
        "notes": "Marinating the chicken is essential — improves digestibility. Light and nourishing. Can be used as both lunch and a lighter dinner.",
        "is_tea": False,
    },
    {
        "name": "Simple Fish with Vegetables",
        "meal_type": "Lunch",
        "dosha_good_for": "Vata, Pitta",
        "dosha_avoid": None,
        "ingredients": "Fish fillet, zucchini or asparagus, turmeric, coriander powder, ginger, olive oil or ghee",
        "instructions": "Marinate fish with turmeric, coriander, and ginger. Cook fish in a pan with a little oil. Sauté vegetables separately. Serve together with barley or rice.",
        "notes": "Fresh fish is preferred. Marinating with turmeric reduces Ama and improves digestibility. White fish is lighter for the gut.",
        "is_tea": False,
    },
    {
        "name": "Coriander-Barley Tea",
        "meal_type": "Drink",
        "dosha_good_for": "Pitta, Kapha, Vata",
        "dosha_avoid": None,
        "ingredients": "1 tsp coarsely ground barley, 1 tsp coriander seeds (daniya), 2 cups water",
        "instructions": "Coarsely grind barley and coriander seeds together. Boil 1 teaspoon of mixture in water for several minutes. Strain and drink warm.",
        "notes": "Prescribed specifically for Shuva's urinary tract issues. Drink 2–3 times daily. Coriander is cooling and soothing for the bladder; barley is a classical Ayurvedic diuretic.",
        "is_tea": True,
    },
    {
        "name": "Licorice Tea",
        "meal_type": "Drink",
        "dosha_good_for": "Vata, Pitta",
        "dosha_avoid": "Kapha (limit frequency)",
        "ingredients": "Licorice root (mulethi) or licorice tea bag, hot water",
        "instructions": "Steep licorice root or tea bag in hot water for 3–5 minutes. Drink warm.",
        "notes": "Soothes respiratory and digestive irritation. Particularly useful for Shuva's acid reflux and ear/sinus congestion. Rotate with Tulsi and Coriander-Barley teas.",
        "is_tea": True,
    },
]


async def get_or_create_supplement(db: AsyncSession, data: dict) -> Supplement:
    result = await db.execute(select(Supplement).where(Supplement.name == data["name"]))
    s = result.scalars().first()
    if not s:
        s = Supplement(**data)
        db.add(s)
        await db.flush()
    return s


async def get_or_create_recipe(db: AsyncSession, data: dict) -> Recipe:
    result = await db.execute(select(Recipe).where(Recipe.name == data["name"]))
    r = result.scalars().first()
    if not r:
        r = Recipe(**data)
        db.add(r)
        await db.flush()
    return r


async def seed_demo():
    async with AsyncSessionLocal() as db:
        # ── 1. Demo practitioner ─────────────────────────────────────────────
        result = await db.execute(select(Practitioner).where(Practitioner.email == DEMO_EMAIL))
        practitioner = result.scalars().first()
        if not practitioner:
            practitioner = Practitioner(
                name="Meenakshi Sharma",
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                practice_name="Meenakshi Ayurveda",
                designation="Vaidya, BAMS",
                bio="Classical Ayurvedic practitioner specialising in chronic disease management, digestive health, and respiratory conditions. 12 years of clinical experience.",
                subscription_tier=SubscriptionTier.PRACTICE,
                subscription_active=True,
                email_verified=True,
            )
            db.add(practitioner)
            await db.flush()
            print(f"Created demo practitioner: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo practitioner already exists: {DEMO_EMAIL}")

        # ── 2. Patient: Shuva Mukhopadhyay ──────────────────────────────────
        result = await db.execute(
            select(Patient)
            .options(selectinload(Patient.health_profile), selectinload(Patient.checkin_token))
            .where(
                Patient.practitioner_id == practitioner.id,
                Patient.first_name == "Shuva",
                Patient.last_name == "Mukhopadhyay",
            )
        )
        patient = result.scalars().first()

        if not patient:
            patient = Patient(
                practitioner_id=practitioner.id,
                first_name="Shuva",
                last_name="Mukhopadhyay",
                dob=date(1984, 4, 23),
                sex="M",
                location="Ocala, Florida",
                occupation="High-stress work environment (long hours)",
                weight_lbs=175.0,
                exercise_notes="Weight lifting ~4x/week, abdominal exercises ~3x/week. Limited cardiovascular activity currently.",
                diet_pattern="Primarily non-vegetarian (chicken, fish, shrimp daily). Occasional vegetarian meals. Inconsistent meal timing. Nighttime snacking.",
                sleep_notes="Irregular sleep schedule. Work stress disrupts sleep rhythm.",
                stress_level="HIGH",
            )
            db.add(patient)
            await db.flush()
            print(f"Created patient: {patient.first_name} {patient.last_name} (id={patient.id})")

            # ── Health profile ────────────────────────────────────────────
            hp = HealthProfile(
                patient_id=patient.id,
                # Ayurvedic
                dosha_primary="Kapha-Vata",
                dosha_secondary="Pitta",
                dosha_imbalances="Kapha accumulation in respiratory and sinus channels. Vata disturbance in urinary tract and nervous system. Agni imbalance contributing to gut inflammation.",
                agni_assessment="Vishama Agni (irregular digestive fire) — intermittent bloating, reflux, and variable appetite.",
                ama_assessment="Moderate — gut inflammation, reflux, and post-meal heaviness suggest Ama accumulation in GI tract.",
                prakriti_notes="Kapha-Vata prakriti. Kapha provides strong physical constitution and endurance; Vata brings intensity and creativity under stress.",
                vikriti_notes="Current imbalance: Kapha elevated in upper respiratory tract and sinuses; Vata aggravated in urinary tract due to past trauma and irregular lifestyle. Secondary Pitta elevation from high-stress work.",
                # Clinical
                chief_complaints=(
                    "1. Chronic ear infections associated with partially perforated eardrums.\n"
                    "2. Recurrent urinary issues — frequent urination and sensation of incomplete bladder emptying.\n"
                    "3. History of urethral injury from childhood sports contributing to ongoing urinary symptoms.\n"
                    "4. Recurrent bladder infections.\n"
                    "5. Digestive discomfort including gut inflammation, occasional acid reflux, and abdominal swelling after long work hours.\n"
                    "6. Sinus congestion leading to ear infections.\n"
                    "7. Allergies, asthma, and breathing difficulty.\n"
                    "8. Fatigue and body inflammation after prolonged work periods."
                ),
                medical_history=(
                    "Childhood urethral stricture with surgical intervention following football injury. "
                    "Recurrent urinary tract infections. Chronic ear infections due to eardrum perforation. "
                    "Allergies and respiratory congestion. Currently on Vyvanse. Recent weight reduction of ~20 lbs."
                ),
                current_medications="Vyvanse (ADHD medication)",
                allergies="Reported allergic tendencies — elevated eosinophils at 10.3% suggesting allergic or inflammatory response.",
                # Labs
                cholesterol_total=184.0,
                hdl=54.0,
                ldl=116.0,
                hemoglobin=16.4,
                hematocrit=50.5,
                eosinophils_pct=10.3,
                glucose=89.0,
                hba1c=5.5,
                testosterone=1608.0,
                tsh=2.94,
                psa=1.05,
                creatinine=1.27,
                egfr=73.0,
                lab_date=date(2025, 3, 1),
                lab_notes=(
                    "LDL mildly elevated (116, optimal <100). Eosinophils elevated at 10.3% — correlates with allergic/inflammatory load. "
                    "Testosterone elevated at 1608 ng/dL — monitor. Hematocrit 50.5% upper normal. "
                    "Kidney function adequate (eGFR 73). All other markers within normal range."
                ),
                # Ashtavidha
                nadi_notes="Kapha-Vata nadi — slow and irregular pattern. Occasional Pitta surges during stress.",
                jihwa_notes="Moderate white coating on tongue — indicates Ama in GI tract. Slightly swollen edges.",
                mutra_notes="Frequent urination, incomplete emptying sensation. History of structural injury (urethral stricture).",
                mala_notes="Inconsistent bowel movements. Occasional constipation followed by loose stools — Vishama pattern.",
            )
            db.add(hp)
            await db.flush()

            # ── Check-in token ────────────────────────────────────────────
            tok = CheckInToken(patient_id=patient.id)
            db.add(tok)
            await db.flush()

        else:
            print(f"Patient Shuva already exists (id={patient.id}), skipping recreation.")
            hp = patient.health_profile
            tok = patient.checkin_token

        # ── 3. Supplements ───────────────────────────────────────────────────
        supp_objects = []
        for s_data in SHUVA_SUPPLEMENTS:
            s = await get_or_create_supplement(db, s_data)
            supp_objects.append(s)
            print(f"  Supplement: {s.name}")

        # ── 4. Recipes ───────────────────────────────────────────────────────
        # Also add Tulsi Tea from library if not already there
        tulsi_result = await db.execute(select(Recipe).where(Recipe.name.ilike("%tulsi%")))
        tulsi = tulsi_result.scalars().first()

        recipe_objects = []
        for r_data in SHUVA_RECIPES:
            r = await get_or_create_recipe(db, r_data)
            recipe_objects.append(r)
            print(f"  Recipe: {r.name}")
        if tulsi:
            recipe_objects.insert(0, tulsi)

        # ── 5. Care plan ─────────────────────────────────────────────────────
        result = await db.execute(
            select(ConsultationPlan).where(
                ConsultationPlan.patient_id == patient.id,
                ConsultationPlan.active == True,
            )
        )
        plan = result.scalars().first()

        if not plan:
            plan_start = date.today() - timedelta(days=21)
            plan = ConsultationPlan(
                patient_id=patient.id,
                title="Initial Protocol — Shuva",
                active=True,
                duration_weeks=3,
                start_date=plan_start,
                foods_to_include=(
                    "Warm cooked meals as primary diet. Barley as main grain where possible. "
                    "Cooked vegetables with moderate spices. Well-prepared chicken or fish (always marinated). "
                    "Warm breakfast daily within 1 hour of waking.\n\n"
                    "Recommended vegetables: zucchini, bottle gourd (lauki), ridge gourd, carrots, "
                    "green beans, spinach, asparagus, cabbage, pumpkin, sweet potato (small quantity). "
                    "Cook or sauté — avoid raw salads while digestion is inflamed.\n\n"
                    "Recommended spices: cumin, coriander, turmeric, ginger. "
                    "Nuts: almonds (6–8), Brazil nut (1) for breakfast. Dried fruit: figs, dates (in moderation)."
                ),
                foods_to_avoid=(
                    "Yogurt — aggravates Kapha and digestive inflammation.\n"
                    "Fermented foods (kimchi, etc.) — aggravates mucus accumulation.\n"
                    "Cold or refrigerated foods — disrupts digestive warmth (Agni).\n"
                    "Beetroot juice — excess sugar spike.\n"
                    "Excess sugar from juices and sweets.\n"
                    "Cold beverages during meals.\n"
                    "Large amounts of raw salads while gut is inflamed.\n"
                    "Late-night heavy meals — no snacking after 8pm."
                ),
                lifestyle_notes=(
                    "Maintain regular meal timing — eat at consistent times each day. "
                    "Avoid late-night snacking. Finish dinner before 8pm.\n\n"
                    "Continue strength training (4x/week). ADD cardiovascular activity: "
                    "brisk walking or light jogging 3–4 times per week.\n\n"
                    "Aim for consistent sleep schedule — same wake time daily. "
                    "Reduce caffeine and nicotine during heavy work periods when possible.\n\n"
                    "For daughter's respiratory symptoms: pinch of pippali (long pepper) powder "
                    "mixed in milk, ghee, or honey once or twice daily."
                ),
                breathing_notes=(
                    "Morning breathing practice — 5 to 10 minutes daily:\n"
                    "1. Sit comfortably, spine upright.\n"
                    "2. Slow nasal breathing only.\n"
                    "3. Inhale for 4 seconds.\n"
                    "4. Exhale for 6 seconds.\n"
                    "5. Continue for 5–10 minutes.\n\n"
                    "This helps regulate nervous system tone, supports the parasympathetic response, "
                    "and improves respiratory function over time."
                ),
                nasal_care_notes=(
                    "Daily nasal lubrication (Nasya) — each morning:\n"
                    "Apply 1–2 drops of warm sesame oil or ghee in each nostril.\n"
                    "Best done after morning breathing practice while still sitting.\n\n"
                    "Benefits: reduces nasal dryness, soothes irritated mucous membranes, "
                    "supports sinus comfort, and may reduce frequency of ear infections over time."
                ),
                followup_notes=(
                    "Follow this plan for 2–3 weeks. Monitor and report:\n"
                    "• Digestion — reflux, bloating, regularity\n"
                    "• Urinary symptoms — frequency, incomplete emptying, any discomfort\n"
                    "• Sinus and respiratory symptoms — congestion, ear discomfort, breathing\n"
                    "• Overall energy levels\n\n"
                    "We will reassess and adjust the protocol based on how your body responds. "
                    "WhatsApp Meenakshi with any questions or significant changes."
                ),
            )
            db.add(plan)
            await db.flush()
            print(f"Created care plan: {plan.title}")

            # Supplement dosing details
            supp_dosing = [
                {"dose": "½ tsp",    "timing": "Before meals",  "frequency": "Twice daily", "special_notes": "Take with warm water. Classical digestive formula — take consistently."},
                {"dose": "¼ tsp",    "timing": "After meals",   "frequency": "Twice daily", "special_notes": "Anti-inflammatory support. Take with warm water after eating."},
                {"dose": "¼ tsp",    "timing": "After meals",   "frequency": "Twice daily", "special_notes": "Respiratory tract support. Take with warm water after eating."},
                {"dose": "1 tablet", "timing": "After meals",   "frequency": "Twice daily", "special_notes": "Urinary tract support. Take with warm water after meals."},
            ]
            for supp, dosing in zip(supp_objects, supp_dosing):
                ps = PlanSupplement(plan_id=plan.id, supplement_id=supp.id, **dosing)
                db.add(ps)

            # Recipes with meal slots
            recipe_slots = [
                ("Breakfast Option 1", tulsi if tulsi else None),
                ("Breakfast Option 2", None),
                ("Breakfast Option 3", None),
                ("Main Lunch", None),
                ("Lunch / Dinner", None),
                ("Lunch", None),
                ("Morning & Afternoon", None),
                ("Rotate Daily", None),
            ]
            for recipe, slot_info in zip(recipe_objects[:8], recipe_slots):
                slot = slot_info[0]
                pr = PlanRecipe(plan_id=plan.id, recipe_id=recipe.id, meal_slot=slot)
                db.add(pr)

            await db.flush()
            print(f"Added {len(supp_objects)} supplements and {min(len(recipe_objects), 8)} recipes to plan")
        else:
            print("Care plan already exists, skipping.")

        # ── 6. 21 days of check-in history ───────────────────────────────────
        result = await db.execute(
            select(DailyCheckIn).where(DailyCheckIn.patient_id == patient.id)
        )
        existing_checkins = result.scalars().all()

        if not existing_checkins:
            print("Creating 21 days of check-in history...")
            token_result = await db.execute(
                select(CheckInToken).where(CheckInToken.patient_id == patient.id)
            )
            token_obj = token_result.scalars().first()

            today = date.today()
            for i in range(21, 0, -1):
                checkin_date = today - timedelta(days=i)
                week = (21 - i) // 7  # 0, 1, 2

                # Compliance improves week over week
                base_compliance = [0.55, 0.72, 0.85][week]

                def yn(prob: float) -> bool:
                    return random.random() < prob

                # Symptom scores improve over time (1=worst, 5=best)
                def score(base: float, noise: float = 0.8) -> int:
                    raw = base + random.uniform(-noise, noise)
                    return max(1, min(5, round(raw)))

                week_scores = [
                    {"digestion": 2.2, "urinary": 1.8, "sinus": 2.0, "energy": 2.0},
                    {"digestion": 3.0, "urinary": 2.5, "sinus": 2.8, "energy": 2.8},
                    {"digestion": 3.8, "urinary": 3.2, "sinus": 3.5, "energy": 3.7},
                ][week]

                # Skip ~2 days randomly over the 3 weeks (no check-in)
                if random.random() < 0.09:
                    continue

                ci = DailyCheckIn(
                    patient_id=patient.id,
                    date=checkin_date,
                    # Morning
                    warm_water=yn(base_compliance + 0.15),
                    breathing_exercise=yn(base_compliance - 0.1),
                    nasal_oil=yn(base_compliance - 0.2),
                    # Breakfast
                    warm_breakfast=yn(base_compliance + 0.1),
                    avoided_cold_food=yn(base_compliance + 0.05),
                    avoided_yogurt=yn(base_compliance + 0.1),
                    # Herbal tea
                    herbal_tea_am=yn(base_compliance + 0.05),
                    # Lunch
                    warm_lunch=yn(base_compliance + 0.1),
                    included_barley=yn(base_compliance - 0.05),
                    no_cold_drinks=yn(base_compliance + 0.1),
                    # Dinner
                    warm_dinner=yn(base_compliance),
                    dinner_before_8pm=yn(base_compliance - 0.1),
                    # Supplements
                    supplements_am=yn(base_compliance + 0.1),
                    supplements_pm=yn(base_compliance + 0.05),
                    # Lifestyle — cardio only 3-4x/week
                    cardio_today=yn(0.5),
                    consistent_sleep=yn(base_compliance - 0.05),
                    # Symptom scores (1-5, higher=better)
                    digestion_score=score(week_scores["digestion"]),
                    urinary_score=score(week_scores["urinary"]),
                    sinus_score=score(week_scores["sinus"]),
                    energy_score=score(week_scores["energy"]),
                    notes=None,
                )
                db.add(ci)

            await db.flush()
            print("21-day check-in history created.")
        else:
            print(f"Check-ins already exist ({len(existing_checkins)} records), skipping.")

        # ── 7. Follow-up ─────────────────────────────────────────────────────
        result = await db.execute(
            select(FollowUp).where(
                FollowUp.patient_id == patient.id,
                FollowUp.completed_at == None,
            )
        )
        existing_followup = result.scalars().first()

        if not existing_followup:
            followup_date = date.today() + timedelta(days=2)
            fu = FollowUp(
                patient_id=patient.id,
                practitioner_id=practitioner.id,
                scheduled_date=followup_date,
                reason="3-week protocol review",
                notes=(
                    "Reassess: digestion, urinary symptoms, sinus/respiratory symptoms, energy levels. "
                    "Review lab markers if new results available. "
                    "Adjust supplement timing and dosing based on response. "
                    "Consider adding Triphala if bowel regularity remains an issue."
                ),
            )
            db.add(fu)
            await db.flush()
            print(f"Scheduled follow-up: {followup_date}")
        else:
            print("Follow-up already scheduled, skipping.")

        # ── 8. Dosha Assessment ──────────────────────────────────────────────
        result = await db.execute(
            select(DoshaAssessment).where(DoshaAssessment.patient_id == patient.id)
        )
        existing_assessment = result.scalars().first()

        if not existing_assessment:
            assessment = DoshaAssessment(
                patient_id=patient.id,
                practitioner_id=practitioner.id,
                # Prakriti: Kapha-Vata (K dominant, V secondary)
                prakriti_vata=7,
                prakriti_pitta=4,
                prakriti_kapha=9,
                prakriti_responses={
                    "body_frame": "kapha", "body_weight": "kapha", "skin": "vata",
                    "hair": "kapha", "eyes": "kapha", "appetite": "vata",
                    "digestion": "vata", "thirst": "pitta", "bowel_habits": "vata",
                    "sleep": "kapha", "dreams": "vata", "speech": "vata",
                    "mental_activity": "vata", "memory": "kapha", "emotions": "vata",
                    "stress_response": "vata", "activity_level": "pitta",
                    "temperature": "kapha", "sweating": "pitta", "joints": "kapha",
                },
                # Vikriti: Kapha elevated (respiratory), Vata aggravated (urinary)
                vikriti_vata=7,
                vikriti_pitta=4,
                vikriti_kapha=8,
                vikriti_responses={
                    "anxiety": 1, "insomnia": 1, "dry_skin": 0, "constipation": 2,
                    "joint_pain": 0, "cold_hands": 0, "weight_loss": 0,
                    "acid_reflux": 2, "inflammation": 1, "irritability": 1,
                    "excessive_heat": 0, "loose_stools": 1, "burning_eyes": 0, "excessive_sweating": 0,
                    "congestion": 3, "weight_gain": 1, "lethargy": 2,
                    "excess_mucus": 2, "sluggish_digestion": 1, "depression": 0, "attachment": 0,
                },
                agni_type="Vishama Agni",
                ama_level="Moderate",
                agni_responses={
                    "appetite_pattern": "Vishama Agni",
                    "post_meal": "Vishama Agni",
                },
                ama_responses={
                    "tongue_coating": 2, "body_odor": 1, "stool_quality": 2, "energy": 2,
                },
                ashtavidha_responses={
                    "nadi": {"finding": "Mixed / dual pulse", "notes": "Kapha-Vata nadi — slow, occasionally irregular. Pitta surges during stress."},
                    "jihwa": {"finding": "Swollen, thick white coating (Kapha)", "notes": "Moderate white coating indicates Ama in GI tract. Swollen edges."},
                    "mutra": {"finding": "Scanty, clear, frequent (Vata)", "notes": "Frequent urination, incomplete emptying. History of urethral stricture."},
                    "mala": {"finding": "Dry, hard, irregular (Vata)", "notes": "Inconsistent bowel movements. Vishama pattern — alternating constipation and loose stools."},
                    "shabda": {"finding": "Normal / mixed", "notes": "Normal voice quality."},
                    "sparsha": {"finding": "Dry, rough, cool, thin (Vata)", "notes": "Some dryness noted on extremities."},
                    "drika": {"finding": "Normal / mixed", "notes": "No significant eye findings."},
                    "akriti": {"finding": "Heavy, calm, lethargic (Kapha)", "notes": "Kapha constitution evident in build and demeanor."},
                },
                result_prakriti="Kapha-Vata",
                result_vikriti="Kapha-Vata",
                notes="Initial comprehensive assessment. Kapha-Vata prakriti with Kapha accumulation in respiratory tract and Vata disturbance in urinary system. Vishama Agni with moderate Ama. Priority: address digestive fire, reduce Kapha in sinuses, support urinary tract.",
            )
            db.add(assessment)
            await db.flush()
            print("Created dosha assessment for Shuva")
        else:
            print("Dosha assessment already exists, skipping.")

        # ── 9. Patient 2: Priya Venkatesh (Pitta, new intake) ──────────────────
        result = await db.execute(
            select(Patient)
            .options(selectinload(Patient.health_profile), selectinload(Patient.checkin_token))
            .where(
                Patient.practitioner_id == practitioner.id,
                Patient.first_name == "Priya",
                Patient.last_name == "Venkatesh",
            )
        )
        priya = result.scalars().first()

        if not priya:
            priya = Patient(
                practitioner_id=practitioner.id,
                first_name="Priya",
                last_name="Venkatesh",
                dob=date(1991, 8, 15),
                sex="F",
                email="priya.v@example.com",
                phone="(512) 555-0192",
                location="Bangalore, India (remote)",
                occupation="Software Engineer — high screen time, sedentary",
                weight_lbs=135.0,
                exercise_notes="Yoga 2x/week, occasional walks. Mostly sedentary during work hours.",
                diet_pattern="Vegetarian. Heavy on spicy food, coffee (3-4 cups/day). Skips breakfast frequently. Late dinners.",
                sleep_notes="Difficulty falling asleep. Wakes between 2-3 AM (Pitta time). Average 5-6 hours.",
                stress_level="HIGH",
            )
            db.add(priya)
            await db.flush()
            print(f"Created patient: Priya Venkatesh (id={priya.id})")

            hp_priya = HealthProfile(
                patient_id=priya.id,
                dosha_primary="Pitta",
                dosha_secondary="Vata",
                dosha_imbalances="Pitta aggravation in digestive tract and skin. Secondary Vata disturbance from irregular lifestyle and sleep deprivation.",
                agni_assessment="Tikshna Agni (sharp/excessive) — intense hunger, acid reflux when meals are delayed, irritability when fasting.",
                ama_assessment="Mild — occasional skin breakouts and coated tongue in morning suggest mild Ama.",
                prakriti_notes="Pitta-Vata prakriti. Sharp intellect, driven personality, competitive. Medium frame with warm skin.",
                vikriti_notes="Current Pitta excess: acid reflux, skin rashes, irritability, insomnia during Pitta hours. Vata aggravation from irregular schedule.",
                chief_complaints=(
                    "1. Acid reflux and burning sensation after meals, especially spicy food.\n"
                    "2. Recurring skin rashes on forearms and neck — worse in summer.\n"
                    "3. Irritability and short temper, especially under work deadlines.\n"
                    "4. Insomnia — difficulty falling asleep, waking at 2-3 AM.\n"
                    "5. Tension headaches 2-3 times per week.\n"
                    "6. Eye strain and dryness from prolonged screen time."
                ),
                medical_history="No major surgeries. History of childhood eczema. Occasional migraines since college.",
                current_medications="None. Previously tried OTC antacids.",
                allergies="Mild dust allergy. No food allergies known.",
                nadi_notes="Pitta nadi — sharp, bounding, regular. Slightly fast rate.",
                jihwa_notes="Slightly yellowish coating centrally. Red edges. No significant swelling.",
                mutra_notes="Normal frequency. Slightly dark yellow — indicating mild dehydration.",
                mala_notes="Regular but occasionally loose — Pitta pattern. 1-2 times daily.",
            )
            db.add(hp_priya)
            await db.flush()

            tok_priya = CheckInToken(patient_id=priya.id)
            db.add(tok_priya)
            await db.flush()

            # Dosha assessment for Priya
            priya_assessment = DoshaAssessment(
                patient_id=priya.id,
                practitioner_id=practitioner.id,
                prakriti_vata=6,
                prakriti_pitta=9,
                prakriti_kapha=5,
                prakriti_responses={
                    "body_frame": "pitta", "body_weight": "pitta", "skin": "pitta",
                    "hair": "pitta", "eyes": "pitta", "appetite": "pitta",
                    "digestion": "pitta", "thirst": "pitta", "bowel_habits": "pitta",
                    "sleep": "vata", "dreams": "pitta", "speech": "pitta",
                    "mental_activity": "pitta", "memory": "pitta", "emotions": "pitta",
                    "stress_response": "pitta", "activity_level": "pitta",
                    "temperature": "vata", "sweating": "pitta", "joints": "vata",
                },
                vikriti_vata=5,
                vikriti_pitta=9,
                vikriti_kapha=3,
                vikriti_responses={
                    "anxiety": 1, "insomnia": 2, "dry_skin": 1, "constipation": 0,
                    "joint_pain": 0, "cold_hands": 0, "weight_loss": 0,
                    "acid_reflux": 3, "inflammation": 2, "irritability": 3,
                    "excessive_heat": 2, "loose_stools": 1, "burning_eyes": 2, "excessive_sweating": 1,
                    "congestion": 0, "weight_gain": 0, "lethargy": 0,
                    "excess_mucus": 0, "sluggish_digestion": 0, "depression": 0, "attachment": 0,
                },
                agni_type="Tikshna Agni",
                ama_level="Mild",
                agni_responses={"appetite_pattern": "Tikshna Agni", "post_meal": "Tikshna Agni"},
                ama_responses={"tongue_coating": 1, "body_odor": 0, "stool_quality": 1, "energy": 1},
                ashtavidha_responses={
                    "nadi": {"finding": "Sharp, bounding, regular (Pitta)", "notes": "Pitta nadi with fast rate. Clear and forceful."},
                    "jihwa": {"finding": "Yellow coating, red edges (Pitta)", "notes": "Yellow central coating suggests Pitta in GI. Red edges."},
                    "mutra": {"finding": "Dark yellow, slightly concentrated (Pitta)", "notes": "Mild dehydration, Pitta heat."},
                    "mala": {"finding": "Loose, frequent (Pitta)", "notes": "1-2x daily, occasionally loose. Pitta pattern."},
                    "shabda": {"finding": "Sharp, clear (Pitta)", "notes": "Clear articulation, slightly sharp tone."},
                    "sparsha": {"finding": "Warm, slightly moist (Pitta)", "notes": "Warm skin, slight oiliness."},
                    "drika": {"finding": "Sharp, reddish (Pitta)", "notes": "Slight redness from screen strain."},
                    "akriti": {"finding": "Medium frame, athletic (Pitta)", "notes": "Medium build, proportional."},
                },
                result_prakriti="Pitta-Vata",
                result_vikriti="Pitta",
                notes="Clear Pitta aggravation with secondary Vata disturbance. Priority: cool Pitta in GI and skin, regulate sleep, reduce stimulants (coffee, spicy food). Recommend cooling diet, Pitta-pacifying herbs, and evening wind-down routine.",
            )
            db.add(priya_assessment)
            await db.flush()

            # Scheduled follow-up for Priya
            fu_priya = FollowUp(
                patient_id=priya.id,
                practitioner_id=practitioner.id,
                scheduled_date=date.today() + timedelta(days=5),
                reason="Initial consultation follow-up",
                notes="Review intake findings. Discuss dietary changes and Pitta-pacifying protocol. Set up care plan.",
            )
            db.add(fu_priya)
            await db.flush()
            print("Created Priya Venkatesh — Pitta-Vata, new intake (no care plan)")
        else:
            print(f"Patient Priya already exists (id={priya.id}), skipping.")

        # ── 10. Patient 3: Arjun Patel (Vata, mid-treatment) ──────────────────
        result = await db.execute(
            select(Patient)
            .options(selectinload(Patient.health_profile), selectinload(Patient.checkin_token))
            .where(
                Patient.practitioner_id == practitioner.id,
                Patient.first_name == "Arjun",
                Patient.last_name == "Patel",
            )
        )
        arjun = result.scalars().first()

        if not arjun:
            arjun = Patient(
                practitioner_id=practitioner.id,
                first_name="Arjun",
                last_name="Patel",
                dob=date(1973, 11, 2),
                sex="M",
                email="arjun.patel@example.com",
                phone="(512) 555-0847",
                location="Austin, Texas",
                occupation="Retired teacher — active in community volunteering",
                weight_lbs=148.0,
                exercise_notes="Daily morning walks (30 min). Gentle stretching. No heavy exercise.",
                diet_pattern="Mostly vegetarian with occasional eggs. Prefers warm, cooked food. Eats regularly but portions are small.",
                sleep_notes="Falls asleep easily but wakes early (4-5 AM). Light sleeper. Dreams frequently.",
                stress_level="MODERATE",
            )
            db.add(arjun)
            await db.flush()
            print(f"Created patient: Arjun Patel (id={arjun.id})")

            hp_arjun = HealthProfile(
                patient_id=arjun.id,
                dosha_primary="Vata",
                dosha_secondary="Pitta",
                dosha_imbalances="Vata aggravation in joints (Asthi dhatu) and nervous system. Mild Pitta in skin from sun exposure.",
                agni_assessment="Vishama Agni (variable) — appetite fluctuates, sometimes skips meals without hunger.",
                ama_assessment="Mild — morning stiffness and occasional tongue coating suggest low-grade Ama.",
                prakriti_notes="Vata-Pitta prakriti. Thin frame, creative mind, enthusiastic. Quick to learn, quick to forget.",
                vikriti_notes="Current Vata excess in joints (stiffness, cracking), nervous system (anxiety, light sleep), and colon (constipation, gas).",
                chief_complaints=(
                    "1. Joint stiffness in knees and fingers — worse in morning and cold weather.\n"
                    "2. Mild anxiety — worry about health, family, future.\n"
                    "3. Insomnia — wakes at 4-5 AM, cannot return to sleep.\n"
                    "4. Dry, flaky skin — especially hands, elbows, and shins.\n"
                    "5. Constipation — irregular bowel movements, hard stools every 2-3 days.\n"
                    "6. Occasional tinnitus (ringing in ears)."
                ),
                medical_history="Mild osteoarthritis diagnosed 3 years ago. No surgeries. Family history of Type 2 diabetes.",
                current_medications="Glucosamine supplement (OTC). Vitamin D 2000 IU daily.",
                allergies="None known.",
                nadi_notes="Vata nadi — thin, irregular, thread-like. Variable rate.",
                jihwa_notes="Thin white coating. Slightly dry. Mild tremor.",
                mutra_notes="Normal frequency but scanty volume. Clear to light yellow.",
                mala_notes="Irregular — every 2-3 days. Hard, dry, pellet-like stools. Vata pattern.",
            )
            db.add(hp_arjun)
            await db.flush()

            tok_arjun = CheckInToken(patient_id=arjun.id)
            db.add(tok_arjun)
            await db.flush()

            # Dosha assessment for Arjun
            arjun_assessment = DoshaAssessment(
                patient_id=arjun.id,
                practitioner_id=practitioner.id,
                prakriti_vata=9,
                prakriti_pitta=5,
                prakriti_kapha=6,
                prakriti_responses={
                    "body_frame": "vata", "body_weight": "vata", "skin": "vata",
                    "hair": "vata", "eyes": "pitta", "appetite": "vata",
                    "digestion": "vata", "thirst": "vata", "bowel_habits": "vata",
                    "sleep": "vata", "dreams": "vata", "speech": "vata",
                    "mental_activity": "vata", "memory": "vata", "emotions": "vata",
                    "stress_response": "vata", "activity_level": "kapha",
                    "temperature": "vata", "sweating": "kapha", "joints": "vata",
                },
                vikriti_vata=10,
                vikriti_pitta=4,
                vikriti_kapha=3,
                vikriti_responses={
                    "anxiety": 3, "insomnia": 2, "dry_skin": 3, "constipation": 3,
                    "joint_pain": 2, "cold_hands": 2, "weight_loss": 1,
                    "acid_reflux": 0, "inflammation": 1, "irritability": 0,
                    "excessive_heat": 0, "loose_stools": 0, "burning_eyes": 0, "excessive_sweating": 0,
                    "congestion": 0, "weight_gain": 0, "lethargy": 0,
                    "excess_mucus": 0, "sluggish_digestion": 0, "depression": 1, "attachment": 0,
                },
                agni_type="Vishama Agni",
                ama_level="Mild",
                agni_responses={"appetite_pattern": "Vishama Agni", "post_meal": "Vishama Agni"},
                ama_responses={"tongue_coating": 1, "body_odor": 0, "stool_quality": 2, "energy": 1},
                ashtavidha_responses={
                    "nadi": {"finding": "Thin, irregular, thread-like (Vata)", "notes": "Classic Vata nadi — serpentine, variable."},
                    "jihwa": {"finding": "Thin white coating, dry (Vata)", "notes": "Dryness and thin coating indicate Vata in GI."},
                    "mutra": {"finding": "Scanty, clear (Vata)", "notes": "Low volume, clear. Vata pattern."},
                    "mala": {"finding": "Dry, hard, irregular (Vata)", "notes": "Hard pellet stools every 2-3 days. Classic Vata constipation."},
                    "shabda": {"finding": "Soft, hesitant (Vata)", "notes": "Quiet voice, trails off mid-sentence occasionally."},
                    "sparsha": {"finding": "Dry, rough, cool, thin (Vata)", "notes": "Cool dry skin, especially extremities."},
                    "drika": {"finding": "Normal / mixed", "notes": "Slightly dull. No redness."},
                    "akriti": {"finding": "Thin, light frame (Vata)", "notes": "Thin, angular frame. Visible joints."},
                },
                result_prakriti="Vata-Pitta",
                result_vikriti="Vata",
                notes="Significant Vata aggravation — joints, colon, nervous system. Priority: ground Vata with warm oil, warm food, regularity. Ashwagandha for nervous system. Triphala for bowel regularity. Sesame oil abhyanga.",
            )
            db.add(arjun_assessment)
            await db.flush()

            # Care plan for Arjun (4 weeks, started 10 days ago)
            arjun_plan_start = date.today() - timedelta(days=10)
            arjun_plan = ConsultationPlan(
                patient_id=arjun.id,
                title="Vata-Balancing Protocol — Arjun",
                active=True,
                duration_weeks=4,
                start_date=arjun_plan_start,
                foods_to_include=(
                    "Warm, moist, cooked foods as primary diet. Favor sweet, sour, salty tastes.\n"
                    "Ghee liberally — 1 tsp with each meal. Warm milk with nutmeg before bed.\n"
                    "Soups, stews, khichdi, oatmeal, rice porridge.\n"
                    "Cooked root vegetables: sweet potato, beets, carrots, pumpkin.\n"
                    "Sesame oil for cooking. Almonds (soaked), dates, figs.\n"
                    "Ginger tea throughout the day for Agni support."
                ),
                foods_to_avoid=(
                    "Raw salads, cold foods, and iced beverages.\n"
                    "Dry, crunchy snacks (crackers, chips, popcorn).\n"
                    "Beans and legumes (except mung dal and red lentils).\n"
                    "Excess bitter and astringent foods.\n"
                    "Caffeine — aggravates Vata and anxiety.\n"
                    "Frozen or leftover food."
                ),
                lifestyle_notes=(
                    "Daily oil massage (Abhyanga) with warm sesame oil — 15 min before morning shower.\n"
                    "Maintain strict daily routine (Dinacharya): wake, eat, sleep at same times.\n"
                    "Evening wind-down: warm bath, gentle stretching, calming music.\n"
                    "Avoid excessive travel, multitasking, or overstimulation.\n"
                    "Gentle walking continues — avoid vigorous exercise."
                ),
                breathing_notes=(
                    "Nadi Shodhana (alternate nostril breathing) — 5 minutes morning and evening.\n"
                    "Calming, grounding practice. Do not rush.\n"
                    "Follow with 2-3 minutes of quiet sitting."
                ),
                nasal_care_notes=(
                    "Nasya: 2 drops warm sesame oil in each nostril every morning.\n"
                    "Helps with Vata in head — supports against tinnitus and anxiety."
                ),
                followup_notes=(
                    "Follow this protocol for 4 weeks. Monitor:\n"
                    "• Joint stiffness — morning severity, range of motion\n"
                    "• Bowel regularity — frequency, consistency\n"
                    "• Sleep quality — waking time, restfulness\n"
                    "• Anxiety levels — frequency of worry episodes\n\n"
                    "Will reassess Agni, Ama, and joint comfort at 4-week mark."
                ),
            )
            db.add(arjun_plan)
            await db.flush()

            # Ashwagandha supplement for Arjun
            ashwagandha_data = {
                "name": "Ashwagandha",
                "name_sanskrit": "Ashwagandha (Withania somnifera)",
                "category": "Nervine / Adaptogen",
                "purpose": "Calms Vata in the nervous system. Supports sleep, reduces anxiety, strengthens joints and muscles. Classical Rasayana.",
                "dosha_effect": "Reduces Vata and Kapha, may mildly increase Pitta in excess",
                "typical_dose": "½ tsp powder or 1 capsule (500mg) twice daily",
                "cautions": "Avoid in acute infections or high Ama. Use cautiously in high Pitta.",
                "is_classical": True,
            }
            ashwagandha = await get_or_create_supplement(db, ashwagandha_data)
            ps_ashwagandha = PlanSupplement(
                plan_id=arjun_plan.id,
                supplement_id=ashwagandha.id,
                dose="½ tsp",
                timing="After meals",
                frequency="Twice daily",
                special_notes="Calming adaptogen for Vata. Take with warm milk or ghee for best absorption.",
            )
            db.add(ps_ashwagandha)

            # Triphala for Arjun
            triphala_data = {
                "name": "Triphala",
                "name_sanskrit": "Triphala (Three Fruits)",
                "category": "Digestive / Detox",
                "purpose": "Gentle bowel regulator. Supports digestion and elimination without dependency. Classical Rasayana.",
                "dosha_effect": "Balances all three doshas (Tridoshic)",
                "typical_dose": "½ tsp powder at bedtime with warm water",
                "cautions": "Reduce dose if loose stools occur. Avoid during pregnancy.",
                "is_classical": True,
            }
            triphala = await get_or_create_supplement(db, triphala_data)
            ps_triphala = PlanSupplement(
                plan_id=arjun_plan.id,
                supplement_id=triphala.id,
                dose="½ tsp",
                timing="Bedtime",
                frequency="Once daily",
                special_notes="Take with warm water before sleep. Helps regulate bowel movements gently.",
            )
            db.add(ps_triphala)
            await db.flush()
            print(f"Created care plan for Arjun: {arjun_plan.title}")

            # 10 days of check-ins for Arjun
            print("Creating 10 days of check-in history for Arjun...")
            today = date.today()
            for i in range(10, 0, -1):
                checkin_date = today - timedelta(days=i)
                # Gradual improvement over 10 days
                progress = (10 - i) / 10.0  # 0.0 to 0.9
                base_compliance = 0.60 + progress * 0.20  # 60% → 80%

                def yn_a(prob: float) -> bool:
                    return random.random() < prob

                def score_a(base: float, noise: float = 0.7) -> int:
                    raw = base + random.uniform(-noise, noise)
                    return max(1, min(5, round(raw)))

                base_scores = {
                    "digestion": 2.3 + progress * 1.2,
                    "urinary": 3.5 + progress * 0.3,
                    "sinus": 3.8 + progress * 0.2,
                    "energy": 2.0 + progress * 1.5,
                }

                if random.random() < 0.08:
                    continue

                ci = DailyCheckIn(
                    patient_id=arjun.id,
                    date=checkin_date,
                    warm_water=yn_a(base_compliance + 0.15),
                    breathing_exercise=yn_a(base_compliance + 0.05),
                    nasal_oil=yn_a(base_compliance - 0.10),
                    warm_breakfast=yn_a(base_compliance + 0.10),
                    avoided_cold_food=yn_a(base_compliance + 0.15),
                    avoided_yogurt=yn_a(base_compliance + 0.20),
                    herbal_tea_am=yn_a(base_compliance + 0.10),
                    warm_lunch=yn_a(base_compliance + 0.10),
                    included_barley=yn_a(base_compliance - 0.15),
                    no_cold_drinks=yn_a(base_compliance + 0.10),
                    warm_dinner=yn_a(base_compliance + 0.05),
                    dinner_before_8pm=yn_a(base_compliance + 0.10),
                    supplements_am=yn_a(base_compliance + 0.10),
                    supplements_pm=yn_a(base_compliance + 0.05),
                    cardio_today=yn_a(0.7),
                    consistent_sleep=yn_a(base_compliance - 0.05),
                    digestion_score=score_a(base_scores["digestion"]),
                    urinary_score=score_a(base_scores["urinary"]),
                    sinus_score=score_a(base_scores["sinus"]),
                    energy_score=score_a(base_scores["energy"]),
                    notes=None,
                )
                db.add(ci)

            await db.flush()
            print("10-day check-in history created for Arjun.")

            # Follow-up for Arjun
            fu_arjun = FollowUp(
                patient_id=arjun.id,
                practitioner_id=practitioner.id,
                scheduled_date=date.today() + timedelta(days=18),
                reason="4-week Vata protocol review",
                notes="Assess joint stiffness improvement, bowel regularity, sleep quality, anxiety levels. Consider adding Bala if joints still stiff.",
            )
            db.add(fu_arjun)
            await db.flush()
            print("Created Arjun Patel — Vata-Pitta, mid-treatment (10 days, active plan)")
        else:
            print(f"Patient Arjun already exists (id={arjun.id}), skipping.")

        # ── 11. Seed yoga asanas ─────────────────────────────────────────────
        result = await db.execute(select(YogaAsana).limit(1))
        if not result.scalars().first():
            print("Seeding yoga asanas...")
            SEED_ASANAS = [
                {
                    "name": "Mountain Pose", "name_sanskrit": "Tadasana",
                    "category": "Standing", "level": "Beginner",
                    "description": "Foundation standing pose that improves posture and body awareness.",
                    "instructions": ["Stand with feet together, weight evenly distributed", "Engage thighs, lengthen spine", "Arms at sides, palms forward", "Hold for 30-60 seconds, breathing steadily"],
                    "benefits": "Improves posture, strengthens thighs, ankles and spine. Promotes body awareness.",
                    "dosha_effect": "Balances Vata & Kapha",
                    "therapeutic_focus": ["Posture", "Grounding", "Balance"],
                    "modifications": ["Widen feet for more stability", "Stand against a wall for support"],
                    "contraindications": ["Low blood pressure (hold briefly)", "Headache"],
                    "hold_duration": "30-60 seconds", "repetitions": "3-5 rounds",
                },
                {
                    "name": "Warrior I", "name_sanskrit": "Virabhadrasana I",
                    "category": "Standing", "level": "Beginner",
                    "description": "Powerful standing lunge that builds strength and stamina.",
                    "instructions": ["Step right foot back 3-4 feet", "Bend front knee to 90 degrees over ankle", "Raise arms overhead, palms facing", "Square hips forward, gaze up"],
                    "benefits": "Strengthens legs, opens hips and chest. Builds stamina and concentration.",
                    "dosha_effect": "Reduces Kapha, balances Vata",
                    "therapeutic_focus": ["Strength", "Hip Opening", "Stamina"],
                    "modifications": ["Shorten stance for less intensity", "Hands on hips instead of overhead"],
                    "contraindications": ["High blood pressure", "Heart problems", "Knee injuries"],
                    "hold_duration": "30-60 seconds per side",
                },
                {
                    "name": "Warrior II", "name_sanskrit": "Virabhadrasana II",
                    "category": "Standing", "level": "Beginner",
                    "description": "Open-hip standing pose that builds leg strength and focus.",
                    "instructions": ["Stand wide, turn right foot out 90°", "Bend right knee over ankle", "Extend arms parallel to floor", "Gaze over front fingertips"],
                    "benefits": "Strengthens legs and ankles. Stretches groins, chest and shoulders.",
                    "dosha_effect": "Reduces Kapha, energizes Vata",
                    "therapeutic_focus": ["Strength", "Focus", "Hip Opening"],
                    "modifications": ["Use a chair under front thigh for support"],
                    "contraindications": ["Knee injuries", "High blood pressure"],
                    "hold_duration": "30-60 seconds per side",
                },
                {
                    "name": "Tree Pose", "name_sanskrit": "Vrksasana",
                    "category": "Balance", "level": "Beginner",
                    "description": "Standing balance that develops focus and stability.",
                    "instructions": ["Stand on left leg", "Place right foot on inner left thigh or calf (not knee)", "Bring hands to prayer position or overhead", "Fix gaze on a steady point"],
                    "benefits": "Improves balance, strengthens ankles and legs. Calms the mind.",
                    "dosha_effect": "Grounds Vata, focuses Pitta",
                    "therapeutic_focus": ["Balance", "Focus", "Grounding"],
                    "modifications": ["Foot on calf instead of thigh", "Use a wall for support"],
                    "contraindications": ["Severe balance disorders", "Ankle injuries"],
                    "hold_duration": "30-60 seconds per side",
                },
                {
                    "name": "Cobra Pose", "name_sanskrit": "Bhujangasana",
                    "category": "Prone", "level": "Beginner",
                    "description": "Gentle backbend that strengthens the spine and opens the chest.",
                    "instructions": ["Lie face down, hands under shoulders", "Press into hands, lift chest off floor", "Keep elbows slightly bent", "Draw shoulders back and down"],
                    "benefits": "Strengthens spine, opens chest and lungs. Stimulates abdominal organs.",
                    "dosha_effect": "Reduces Kapha, stimulates Agni",
                    "therapeutic_focus": ["Back Strength", "Chest Opening", "Digestion"],
                    "modifications": ["Baby cobra — only lift a few inches", "Use forearms (Sphinx Pose)"],
                    "contraindications": ["Pregnancy", "Recent abdominal surgery", "Severe back injury"],
                    "hold_duration": "15-30 seconds", "repetitions": "3-5 rounds",
                },
                {
                    "name": "Downward-Facing Dog", "name_sanskrit": "Adho Mukha Svanasana",
                    "category": "Standing", "level": "Beginner",
                    "description": "Full-body stretch and mild inversion that energizes and calms.",
                    "instructions": ["Start on hands and knees", "Tuck toes, lift hips up and back", "Press hands into floor, straighten arms", "Let head hang between arms"],
                    "benefits": "Stretches hamstrings, calves, and shoulders. Strengthens arms and legs. Calms the brain.",
                    "dosha_effect": "Calms Pitta, reduces Kapha",
                    "therapeutic_focus": ["Full Body Stretch", "Inversion", "Energy"],
                    "modifications": ["Bend knees generously", "Use blocks under hands"],
                    "contraindications": ["Carpal tunnel syndrome", "Late-term pregnancy", "High blood pressure (hold briefly)"],
                    "hold_duration": "1-3 minutes",
                },
                {
                    "name": "Child's Pose", "name_sanskrit": "Balasana",
                    "category": "Restorative", "level": "Beginner",
                    "description": "Gentle resting pose that calms the nervous system.",
                    "instructions": ["Kneel on floor, sit on heels", "Fold forward, forehead to floor", "Arms extended forward or alongside body", "Breathe deeply into back body"],
                    "benefits": "Gently stretches hips, thighs, ankles. Calms the brain, relieves stress and fatigue.",
                    "dosha_effect": "Calms Vata & Pitta",
                    "therapeutic_focus": ["Relaxation", "Stress Relief", "Hip Opening"],
                    "modifications": ["Place a pillow between thighs and calves", "Wide knees for belly space"],
                    "contraindications": ["Knee injury (use padding)", "Pregnancy (wide-knee variation)"],
                    "hold_duration": "1-5 minutes",
                },
                {
                    "name": "Seated Forward Fold", "name_sanskrit": "Paschimottanasana",
                    "category": "Seated", "level": "Beginner",
                    "description": "Deep hamstring and back stretch that calms the mind.",
                    "instructions": ["Sit with legs extended forward", "Inhale, lengthen spine", "Exhale, hinge at hips and fold forward", "Hold feet, ankles, or shins"],
                    "benefits": "Stretches spine, shoulders, hamstrings. Calms the brain, reduces anxiety.",
                    "dosha_effect": "Calms Vata & Pitta",
                    "therapeutic_focus": ["Flexibility", "Stress Relief", "Digestion"],
                    "modifications": ["Bend knees slightly", "Use a strap around feet"],
                    "contraindications": ["Back injury", "Disc herniation"],
                    "hold_duration": "1-3 minutes",
                },
                {
                    "name": "Bridge Pose", "name_sanskrit": "Setu Bandhasana",
                    "category": "Supine", "level": "Beginner",
                    "description": "Gentle backbend that opens the chest and strengthens the back.",
                    "instructions": ["Lie on back, bend knees, feet hip-width apart", "Press feet into floor, lift hips", "Clasp hands under back or keep arms at sides", "Hold and breathe steadily"],
                    "benefits": "Strengthens back, glutes, hamstrings. Opens chest and hip flexors.",
                    "dosha_effect": "Stimulates Agni, calms Vata",
                    "therapeutic_focus": ["Back Strength", "Chest Opening", "Energy"],
                    "modifications": ["Place a block under sacrum for support"],
                    "contraindications": ["Neck injury", "Recent back surgery"],
                    "hold_duration": "30-60 seconds", "repetitions": "3-5 rounds",
                },
                {
                    "name": "Corpse Pose", "name_sanskrit": "Savasana",
                    "category": "Restorative", "level": "Beginner",
                    "description": "Final relaxation pose that integrates the practice.",
                    "instructions": ["Lie flat on back, legs slightly apart", "Arms at sides, palms up", "Close eyes, relax every muscle", "Breathe naturally, let go completely"],
                    "benefits": "Deep relaxation, reduces blood pressure, calms the nervous system.",
                    "dosha_effect": "Balances all doshas, especially Vata",
                    "therapeutic_focus": ["Deep Relaxation", "Stress Relief", "Integration"],
                    "modifications": ["Place bolster under knees", "Cover with a blanket for warmth"],
                    "contraindications": [],
                    "hold_duration": "5-15 minutes",
                },
                {
                    "name": "Sun Salutation A", "name_sanskrit": "Surya Namaskar A",
                    "category": "Warm-Up", "level": "Intermediate",
                    "description": "Dynamic sequence that warms the entire body and links breath with movement.",
                    "instructions": ["Mountain → Forward fold → Halfway lift", "Step/jump back to plank → Chaturanga", "Upward Dog → Downward Dog (5 breaths)", "Step forward → Forward fold → Mountain"],
                    "benefits": "Full-body warm-up. Builds heat, improves cardiovascular health, increases flexibility.",
                    "dosha_effect": "Reduces Kapha, balances Vata when done slowly",
                    "therapeutic_focus": ["Full Body", "Cardiovascular", "Flexibility"],
                    "modifications": ["Use knees in plank/chaturanga", "Step instead of jump"],
                    "contraindications": ["Heart conditions", "High blood pressure", "Pregnancy (modified only)"],
                    "repetitions": "3-5 rounds",
                },
                {
                    "name": "Triangle Pose", "name_sanskrit": "Trikonasana",
                    "category": "Standing", "level": "Intermediate",
                    "description": "Standing lateral stretch that opens the side body.",
                    "instructions": ["Stand wide, right foot out 90°", "Extend arms, reach right hand to shin/floor", "Extend left arm to ceiling", "Gaze up at top hand"],
                    "benefits": "Stretches legs, hips, spine. Strengthens thighs, knees, ankles.",
                    "dosha_effect": "Balances Vata & Kapha",
                    "therapeutic_focus": ["Side Body Stretch", "Balance", "Digestion"],
                    "modifications": ["Use a block under bottom hand"],
                    "contraindications": ["Low blood pressure", "Neck problems (look down instead of up)"],
                    "hold_duration": "30-60 seconds per side",
                },
                {
                    "name": "Boat Pose", "name_sanskrit": "Navasana",
                    "category": "Seated", "level": "Intermediate",
                    "description": "Core-strengthening pose that builds abdominal fire.",
                    "instructions": ["Sit with knees bent, feet on floor", "Lean back slightly, lift feet off floor", "Extend legs to 45 degrees (or keep bent)", "Arms parallel to floor, palms facing in"],
                    "benefits": "Strengthens core, hip flexors, and spine. Stimulates Agni.",
                    "dosha_effect": "Reduces Kapha, stimulates Agni",
                    "therapeutic_focus": ["Core Strength", "Digestion", "Willpower"],
                    "modifications": ["Keep knees bent", "Hold behind thighs for support"],
                    "contraindications": ["Pregnancy", "Low back pain", "Recent abdominal surgery"],
                    "hold_duration": "15-30 seconds", "repetitions": "3-5 rounds",
                },
                {
                    "name": "Pigeon Pose", "name_sanskrit": "Eka Pada Rajakapotasana",
                    "category": "Hip Opener", "level": "Intermediate",
                    "description": "Deep hip opener that releases stored tension and emotion.",
                    "instructions": ["From downward dog, bring right knee behind right wrist", "Extend left leg straight back", "Square hips, fold forward over front leg", "Rest on forearms or forehead"],
                    "benefits": "Deep hip flexor and glute stretch. Releases emotional tension.",
                    "dosha_effect": "Calms Vata, releases Pitta",
                    "therapeutic_focus": ["Hip Opening", "Emotional Release", "Flexibility"],
                    "modifications": ["Use a block or blanket under front hip", "Reclined pigeon (figure-4) as alternative"],
                    "contraindications": ["Knee injury", "Sacroiliac issues"],
                    "hold_duration": "1-3 minutes per side",
                },
                {
                    "name": "Spinal Twist", "name_sanskrit": "Ardha Matsyendrasana",
                    "category": "Twist", "level": "Intermediate",
                    "description": "Seated twist that detoxifies and improves spinal mobility.",
                    "instructions": ["Sit with legs extended", "Bend right knee, cross over left leg", "Twist torso to the right, left elbow outside right knee", "Lengthen spine on each inhale, deepen twist on exhale"],
                    "benefits": "Improves spinal mobility. Stimulates digestion and detoxification.",
                    "dosha_effect": "Stimulates Agni, reduces Kapha",
                    "therapeutic_focus": ["Detox", "Spinal Mobility", "Digestion"],
                    "modifications": ["Keep bottom leg straight", "Use hand behind instead of elbow hook"],
                    "contraindications": ["Spinal disc injury", "Pregnancy"],
                    "hold_duration": "30-60 seconds per side",
                },
                {
                    "name": "Shoulder Stand", "name_sanskrit": "Sarvangasana",
                    "category": "Inversion", "level": "Advanced",
                    "description": "Queen of asanas — full inversion that benefits the thyroid and calms the nervous system.",
                    "instructions": ["Lie on back, lift legs overhead", "Support lower back with hands", "Extend legs straight up", "Keep weight on shoulders, not neck"],
                    "benefits": "Stimulates thyroid. Calms the brain, reduces anxiety. Improves circulation.",
                    "dosha_effect": "Calms Vata & Pitta, reduces Kapha",
                    "therapeutic_focus": ["Thyroid", "Inversion", "Calm"],
                    "modifications": ["Legs up the wall as gentle alternative", "Use blankets under shoulders"],
                    "contraindications": ["Neck injury", "High blood pressure", "Glaucoma", "Menstruation", "Pregnancy"],
                    "hold_duration": "1-5 minutes",
                },
                {
                    "name": "Headstand", "name_sanskrit": "Sirsasana",
                    "category": "Inversion", "level": "Advanced",
                    "description": "King of asanas — full inversion that builds strength and clarity.",
                    "instructions": ["Interlace fingers, place forearms on floor", "Place crown of head on floor, cupped by hands", "Walk feet in, lift legs up one at a time or together", "Engage core, press forearms down"],
                    "benefits": "Builds upper body strength. Increases blood flow to brain. Improves focus and balance.",
                    "dosha_effect": "Reduces Kapha, clarifies Pitta mind",
                    "therapeutic_focus": ["Strength", "Focus", "Inversion"],
                    "modifications": ["Practice against a wall", "Dolphin pose as preparation"],
                    "contraindications": ["Neck injury", "High blood pressure", "Glaucoma", "Heart conditions", "Pregnancy"],
                    "hold_duration": "30 seconds to 5 minutes",
                },
                {
                    "name": "Legs Up The Wall", "name_sanskrit": "Viparita Karani",
                    "category": "Restorative", "level": "Beginner",
                    "description": "Gentle inversion that promotes relaxation and reduces swelling.",
                    "instructions": ["Sit with one hip against wall", "Swing legs up the wall as you lie back", "Arms at sides or on belly", "Close eyes and breathe"],
                    "benefits": "Reduces leg swelling, calms the nervous system, relieves lower back tension.",
                    "dosha_effect": "Calms Vata & Pitta",
                    "therapeutic_focus": ["Relaxation", "Circulation", "Recovery"],
                    "modifications": ["Place a bolster under hips", "Bend knees if hamstrings are tight"],
                    "contraindications": ["Glaucoma", "Serious neck problems"],
                    "hold_duration": "5-15 minutes",
                },
                {
                    "name": "Cat-Cow Stretch", "name_sanskrit": "Marjaryasana-Bitilasana",
                    "category": "Warm-Up", "level": "Beginner",
                    "description": "Gentle spinal warm-up that coordinates breath and movement.",
                    "instructions": ["Start on hands and knees", "Inhale: drop belly, lift chest and tailbone (Cow)", "Exhale: round spine, tuck chin and tailbone (Cat)", "Flow between positions with breath"],
                    "benefits": "Warms the spine, improves spinal flexibility. Massages abdominal organs.",
                    "dosha_effect": "Balances Vata, gently stimulates Agni",
                    "therapeutic_focus": ["Spinal Mobility", "Warm-Up", "Breath Awareness"],
                    "modifications": ["Use fists instead of flat hands for wrist issues"],
                    "contraindications": ["Severe neck injury (keep head neutral)"],
                    "repetitions": "10-20 rounds",
                },
                {
                    "name": "Camel Pose", "name_sanskrit": "Ustrasana",
                    "category": "Backbend", "level": "Intermediate",
                    "description": "Deep backbend that opens the entire front body.",
                    "instructions": ["Kneel with knees hip-width apart", "Place hands on lower back, fingers pointing down", "Lift chest and lean back", "Reach for heels if accessible"],
                    "benefits": "Opens chest, hip flexors, and shoulders. Stimulates abdominal organs.",
                    "dosha_effect": "Reduces Kapha, opens Vata in chest",
                    "therapeutic_focus": ["Chest Opening", "Back Flexibility", "Energy"],
                    "modifications": ["Keep hands on lower back", "Use blocks beside ankles"],
                    "contraindications": ["Low back pain", "Neck injury", "High or low blood pressure"],
                    "hold_duration": "15-30 seconds", "repetitions": "2-3 rounds",
                },
            ]

            asana_map = {}
            for data in SEED_ASANAS:
                asana = YogaAsana(**data)
                db.add(asana)
                await db.flush()
                asana_map[data["name"]] = asana.id

            # Seed videos for a few asanas
            SEED_VIDEOS = [
                {
                    "title": "Mountain Pose for Beginners",
                    "url": "https://www.youtube.com/watch?v=2HTvZp5rPrg",
                    "platform": "youtube",
                    "embed_url": "https://www.youtube.com/embed/2HTvZp5rPrg",
                    "thumbnail_url": "https://img.youtube.com/vi/2HTvZp5rPrg/hqdefault.jpg",
                    "duration_display": "3:45",
                    "source_name": "Yoga With Adriene",
                    "is_primary": True,
                    "entity_type": "yoga_asana",
                    "entity_id": asana_map["Mountain Pose"],
                },
                {
                    "title": "Cobra Pose Tutorial",
                    "url": "https://www.youtube.com/watch?v=JDcdhTuycOI",
                    "platform": "youtube",
                    "embed_url": "https://www.youtube.com/embed/JDcdhTuycOI",
                    "thumbnail_url": "https://img.youtube.com/vi/JDcdhTuycOI/hqdefault.jpg",
                    "duration_display": "5:12",
                    "source_name": "Yoga With Adriene",
                    "is_primary": True,
                    "entity_type": "yoga_asana",
                    "entity_id": asana_map["Cobra Pose"],
                },
                {
                    "title": "Sun Salutation A — Step by Step",
                    "url": "https://www.youtube.com/watch?v=73sjOu0g58M",
                    "platform": "youtube",
                    "embed_url": "https://www.youtube.com/embed/73sjOu0g58M",
                    "thumbnail_url": "https://img.youtube.com/vi/73sjOu0g58M/hqdefault.jpg",
                    "duration_display": "8:30",
                    "source_name": "Yoga With Adriene",
                    "is_primary": True,
                    "entity_type": "yoga_asana",
                    "entity_id": asana_map["Sun Salutation A"],
                },
                {
                    "title": "Downward Dog — Common Mistakes",
                    "url": "https://www.youtube.com/watch?v=EC7RGJ975Hk",
                    "platform": "youtube",
                    "embed_url": "https://www.youtube.com/embed/EC7RGJ975Hk",
                    "thumbnail_url": "https://img.youtube.com/vi/EC7RGJ975Hk/hqdefault.jpg",
                    "duration_display": "6:15",
                    "source_name": "Yoga With Adriene",
                    "is_primary": True,
                    "entity_type": "yoga_asana",
                    "entity_id": asana_map["Downward-Facing Dog"],
                },
            ]

            for vdata in SEED_VIDEOS:
                db.add(VideoReference(**vdata))
            await db.flush()
            print(f"Seeded {len(SEED_ASANAS)} yoga asanas and {len(SEED_VIDEOS)} video references.")

            # Assign a couple asanas to Shuva's plan
            result = await db.execute(
                select(ConsultationPlan).where(ConsultationPlan.patient_id == patient.id, ConsultationPlan.active == True)  # noqa: E712
            )
            shuva_plan = result.scalars().first()
            if shuva_plan:
                db.add(PlanYogaAsana(plan_id=shuva_plan.id, asana_id=asana_map["Mountain Pose"], frequency="Daily", notes="Foundation pose for grounding Kapha energy."))
                db.add(PlanYogaAsana(plan_id=shuva_plan.id, asana_id=asana_map["Sun Salutation A"], frequency="Daily", notes="3-5 rounds each morning to build heat and reduce Kapha."))
                db.add(PlanYogaAsana(plan_id=shuva_plan.id, asana_id=asana_map["Cobra Pose"], frequency="Daily", notes="Opens chest, stimulates Agni."))
                await db.flush()
                print("Assigned 3 yoga asanas to Shuva's care plan.")
        else:
            print("Yoga asanas already seeded, skipping.")

        await db.commit()
        print(f"\nDemo seed complete.")
        print(f"  Login:    {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")
        print(f"  Patients: Shuva (21-day history), Priya (new intake), Arjun (10-day mid-treatment)")


if __name__ == "__main__":
    asyncio.run(seed_demo())
