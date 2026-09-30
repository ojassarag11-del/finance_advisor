import os, json
from datetime import date
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
db = SQLAlchemy(app)

CATEGORIES = ["Rent", "Food", "Transport", "Entertainment", "Utilities",
              "Education", "Healthcare", "Shopping", "Other"]
PLAN = {  # share of spendable income per category, by profile
    "salaried":   [.30, .12, .06, .05, .05, .02, .03, .05, .04],
    "student":    [.25, .25, .10, .08, .04, .10, .02, .06, .05],
    "freelancer": [.28, .12, .05, .04, .05, .03, .04, .04, .05],
    "household":  [.27, .18, .06, .03, .08, .08, .05, .04, .04],
}


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)      # YYYY-MM-DD
    source = db.Column(db.String(80), default="Income")
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return dict(id=self.id, day=self.day, source=self.source, amount=self.amount)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    note = db.Column(db.String(120), default="")
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return dict(id=self.id, day=self.day, category=self.category,
                    note=self.note, amount=self.amount)


def month_of(req):
    return req.args.get("month") or date.today().strftime("%Y-%m")


def build_summary(month, profile="salaried", goal=20):
    inc = Income.query.filter(Income.day.startswith(month)).all()
    exp = Expense.query.filter(Expense.day.startswith(month)).all()
    ti, te = sum(i.amount for i in inc), sum(e.amount for e in exp)
    by = {c: 0.0 for c in CATEGORIES}
    for e in exp:
        by[e.category] = by.get(e.category, 0) + e.amount
    pool = ti * (1 - goal / 100)
    shares = PLAN.get(profile, PLAN["salaried"])
    total = sum(shares)
    limits = {c: pool * s / total for c, s in zip(CATEGORIES, shares)}
    return dict(month=month, profile=profile, goal=goal, income=ti, expenses=te,
                saved=ti - te, savings_rate=(ti - te) / ti * 100 if ti else 0,
                by_category=by, limits=limits,
                income_list=[i.to_dict() for i in inc],
                expense_list=[e.to_dict() for e in exp])


def rule_based_advice(s):
    tips = []
    if not s["income"]:
        return ["Add your income for this month to get a personalised budget."]
    over = sorted(((s["by_category"][c] - s["limits"][c], c) for c in CATEGORIES
                   if s["by_category"][c] > s["limits"][c]), reverse=True)
    for diff, c in over[:3]:
        tips.append(f"{c} is ₹{diff:,.0f} over its limit. Trim it next month.")
    if s["saved"] < 0:
        tips.append(f"You spent ₹{-s['saved']:,.0f} more than you earned. Pause discretionary spending.")
    elif s["savings_rate"] >= s["goal"]:
        tips.append("You hit your savings goal. Move the surplus into savings.")
    else:
        tips.append(f"You are {s['goal'] - s['savings_rate']:.1f} points below your savings goal.")
    if s["profile"] == "freelancer":
        tips.append("Build an emergency fund of 6 months of expenses; save more in high-income months.")
    return tips


def gemini_advice(s):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        prompt = (
            "You are a personal finance advisor. Currency is INR. Given this monthly data as JSON, "
            "reply with ONLY a JSON array of 3 to 5 short, specific, actionable tips (strings). "
            "Mention overspent categories and how to reach the savings goal. Profile matters: "
            "student, freelancer (variable income, emergency fund), salaried, or household.\n"
            + json.dumps({k: s[k] for k in ("month", "profile", "goal", "income", "expenses",
                                            "saved", "by_category", "limits")}))
        r = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = r.text.strip().removeprefix("```json").removesuffix("```").strip()
        tips = json.loads(text)
        return [str(t) for t in tips] if isinstance(tips, list) else None
    except Exception as ex:
        app.logger.warning("Gemini failed: %s", ex)
        return None


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.get("/api/summary")
def summary():
    return jsonify(build_summary(month_of(request), request.args.get("profile", "salaried"),
                                 float(request.args.get("goal", 20))))


@app.post("/api/income")
def add_income():
    d = request.get_json(force=True)
    if float(d.get("amount", 0)) <= 0:
        return jsonify(error="Amount must be greater than 0"), 400
    row = Income(day=d.get("day") or date.today().isoformat(),
                 source=d.get("source") or "Income", amount=float(d["amount"]))
    db.session.add(row); db.session.commit()
    return jsonify(row.to_dict()), 201


@app.post("/api/expenses")
def add_expense():
    d = request.get_json(force=True)
    if float(d.get("amount", 0)) <= 0 or d.get("category") not in CATEGORIES:
        return jsonify(error="Valid category and amount required"), 400
    row = Expense(day=d.get("day") or date.today().isoformat(), category=d["category"],
                  note=d.get("note", ""), amount=float(d["amount"]))
    db.session.add(row); db.session.commit()
    return jsonify(row.to_dict()), 201


@app.delete("/api/<kind>/<int:rid>")
def delete_row(kind, rid):
    model = {"income": Income, "expenses": Expense}.get(kind)
    if not model:
        return jsonify(error="Unknown type"), 404
    row = db.session.get(model, rid)
    if row:
        db.session.delete(row); db.session.commit()
    return jsonify(ok=True)


@app.get("/api/advice")
def advice():
    s = build_summary(month_of(request), request.args.get("profile", "salaried"),
                      float(request.args.get("goal", 20)))
    tips = gemini_advice(s) if s["income"] else None
    return jsonify(source="gemini" if tips else "rules", tips=tips or rule_based_advice(s))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
