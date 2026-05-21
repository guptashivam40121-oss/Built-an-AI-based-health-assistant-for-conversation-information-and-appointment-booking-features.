from flask import Flask, render_template, request, jsonify
import wikipedia
import requests
import re
from datetime import datetime

app = Flask(__name__)
chat_history = []

# Medicine reminders stored per user (simple dict)
medicine_reminders = {}

# ---- Helper Functions ----

def get_quote():
    try:
        r = requests.get("https://api.quotable.io/random", timeout=5).json()
        return f"\"{r['content']}\" — {r['author']}"
    except Exception as e:
        return f"Quote API error: {e}"

def get_health_news():
    url = "https://newsapi.org/v2/top-headlines?category=health&country=us&apiKey=YOUR_NEWS_API_KEY"
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])[:3]
        return "\n\n".join(f"{a['title']}\n{a['url']}" for a in articles)
    except Exception as e:
        return f"Error fetching health news: {e}"

def get_medical_info(topic):
    try:
        return wikipedia.summary(topic, sentences=2)
    except wikipedia.exceptions.DisambiguationError as e:
        return f"Ambiguous topic. Try one of these: {', '.join(e.options[:3])}"
    except Exception as e:
        return f"Error: {e}"
def get_diet_for_condition(condition):
    diets = {
        "cancer": """
Diet for Cancer:
- High-protein foods: Eggs, chicken, tofu, fish, nuts
- Fruits and vegetables: Spinach, broccoli, carrots, berries
- Whole grains: Brown rice, oats
- Healthy fats: Avocados, flaxseeds
- Hydration: Water, juices
Avoid: Processed foods, sugary drinks, red meat.
""",
        "diarrhea": """
Diet for Diarrhea:
- BRAT diet: Bananas, Rice, Applesauce, Toast
- Boiled potatoes, carrots, yogurt
- Fluids: Water, coconut water, herbal teas
Avoid: Spicy food, dairy, caffeine, alcohol.
""",
        "fever": """
Diet for Fever:
- Light foods: Khichdi, soups, porridge
- Fruits: Oranges, apples, papaya
- Hydration: Water, lemon water, ORS
Avoid: Oily, fried, cold foods.
""",
        "cold": """
Diet for Cold:
- Warm soups, ginger tea, honey
- Vitamin C: Lemon, oranges, amla
- Turmeric milk, garlic
Avoid: Cold beverages, ice cream, fried foods.
""",
        "typhoid": """
Diet for Typhoid:
- Soft bland foods: Boiled rice, mashed potatoes, bananas
- Soups, oral rehydration solution (ORS)
- Boiled vegetables
Avoid: High-fiber, spicy, fried food.
""",
        "dengue": """
Diet for Dengue:
- Papaya leaves juice (to support platelet count)
- Coconut water, fruit juices
- Porridge, soup, khichdi
Avoid: Caffeine, oily food, processed items.
""",
        "healthy": """
General Healthy Diet:
- 50% vegetables and fruits
- 25% whole grains (oats, brown rice)
- 25% protein (chicken, legumes, tofu)
- Nuts, seeds, and good fats
Avoid: Excess salt, sugar, fried foods. Drink 2-3L water/day.
"""
    }

    # Try to match even if user says "diet for dengue fever"
    for key in diets:
        if key in condition.lower():
            return diets[key]

    return f"Sorry, I don't have diet info for '{condition}'. Please try another condition like cancer, cold, etc."


def get_drugs_for_disease(disease_name):
    url = f"https://api.fda.gov/drug/label.json?search=indications_and_usage:{disease_name}&limit=1"
    try:
        res = requests.get(url).json()
        drug = res["results"][0]
        name = drug["openfda"].get("brand_name", ["Unknown"])[0]
        usage = drug["indications_and_usage"][0][:300]
        return f"Drug: {name}\nUsage: {usage}..."
    except Exception:
        return "Sorry, I couldn't find drug info for that."

def set_medicine_reminder(user_id, time_str):
    medicine_reminders[user_id] = time_str
    return f"Medicine reminder set for {time_str}"

def get_symptoms_from_wikipedia(query):
    keywords = ["symptoms of", "signs of", "what are the symptoms of"]
    disease = None
    for kw in keywords:
        if kw in query:
            disease = query.split(kw)[-1].strip()
            break
    if not disease:
        return None

    try:
        summary = wikipedia.summary(disease, sentences=5)
        for sentence in summary.split('.'):
            if "symptom" in sentence.lower():
                return sentence.strip() + "."
        return f"I found this about {disease}: {summary}"
    except Exception:
        return f"Sorry, I couldn't find information about '{disease}'."

def extract_medicine_time(text):
    match = re.search(r'(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?', text.lower())
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        medicine_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        return medicine_time.strftime("%I:%M %p")

    return None

# ---- Assistant Logic ----

def ai_health_assistant(query):
    query = query.lower()

    if any(greet in query for greet in ["hi", "hello", "hey", "good morning"]):
        return "Hello! I am your AI health assistant. How can I help you?"
    if any(farewell in query for farewell in ["ok bye", "good bye", "bye"]):
        return "I hope you are satisfied. Goodbye!"
    if "quote" in query or "motivat" in query:
        return get_quote()
    if any(greet  in query for greet in ["thank you"]):
        return "Any time you need."
    if "treatment for" in query or "medicine for" in query or "drug for" in query:
        disease = query.split("for")[-1].strip()
        return get_drugs_for_disease(disease)
    if "what is" in query or "information about" in query or "explain" in query or "how to" in query:
        topic = query.replace("what is", "").replace("info on", "").replace("explain", "").replace("more info on ", "").strip()
        return get_medical_info(topic)
    if "hospital near me" in query or "nearby hospital" in query:
        return ('Please enable location and visit: '
                '<a href="https://www.google.com/maps/search/hospitals+near+me" target="_blank">Hospitals Near Me</a>')
    if "book appointment" in query or "schedule appointment" in query:
        return (
            "I can't book appointments directly, but you can try platforms like:\n"
            "🔹 <a href='https://www.practo.com/' target='_blank'>Practo</a>\n"
            "🔹 <a href='https://www.apollo247.com/' target='_blank'>Apollo 24/7</a>\n"
            "🔹 <a href='https://www.1mg.com' target='_blank'>Tata 1mg</a>")
    if "government health facilities" in query or "public health services" in query:
        return (
            "Here are some key government health facilities:\n"
            "🔹 Primary Health Centres (PHCs)\n"
            "🔹 Community Health Centres (CHCs)\n"
            "🔹 District Hospitals\n"
            "🔹 Ayushman Bharat (PM-JAY) – free treatment\n"
            "🔹 eSanjeevani Telemedicine: <a href='https://esanjeevani.in/' target='_blank'>Visit here</a>")
    if "diet for" in query or "food for" in query or "nutrition for" in query:
        condition = query.split("for")[-1].strip()
        return get_diet_for_condition(condition)
    if "set reminder" in query or "medicine time" in query:
        time_str = extract_medicine_time(query)
        if time_str:
            return set_medicine_reminder("user1", time_str)
        else:
            return "Sorry, I couldn't understand the time. Please say something like 'Set reminder at 8 PM'."
    if "cancel reminder" in query or "remove reminder" in query:
        if "user1" in medicine_reminders:
            del medicine_reminders["user1"]
            return "Your medicine reminder has been canceled."
        else:
            return "You don't have any reminder set to cancel."

    # Symptom checker using Wikipedia
    symptom_response = get_symptoms_from_wikipedia(query)
    if symptom_response:
        return symptom_response

    return "Sorry, I couldn't understand. Please ask about a disease, symptom, or request a quote."

# ---- Routes ----

@app.route("/")
def index():
    reminder_time = medicine_reminders.get("user1", "")  # e.g. "10:30 AM"
    greeting = "Hello! I AM YOUR AI DOCTOR X."
    return render_template("index.html", greeting=greeting, reminder_time=reminder_time)

@app.route("/process", methods=["POST"])
def process():
    user_text = request.json.get("text", "")
    if not user_text:
        return jsonify({"response": "Please speak something."})

    response = ai_health_assistant(user_text)
    chat_history.append({"role": "user", "text": user_text})
    chat_history.append({"role": "assistant", "text": response})

    return jsonify({"response": response, "history": chat_history})

if __name__ == "__main__":
    app.run(debug=True)

