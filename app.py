from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import sqlite3
from pathlib import Path
import csv
import io
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_for_local")  # use env var in production

DB_PATH = Path("instance/expenses.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses ORDER BY date DESC")
    rows = cur.fetchall()
    conn.close()

    # Convert fetched sqlite rows into list of dicts so pandas gets proper column names
    try:
        rows_list = [dict(r) for r in rows]  # works whether rows are sqlite3.Row or tuples (dict() will fail for tuples, so except below handles)
    except Exception:
        # fallback: if rows are tuples, fetch column names and build dicts
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(expenses)")
        cols_info = cur.fetchall()
        conn.close()
        col_names = [c[1] for c in cols_info] if cols_info else []
        rows_list = [dict(zip(col_names, r)) for r in rows]

    # Build dataframe safely
    if rows_list:
        df = pd.DataFrame(rows_list)
        # ensure amount and date are present (defensive)
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        else:
            df['amount'] = 0.0
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        else:
            df['date'] = pd.to_datetime(pd.Series([], dtype='datetime64[ns]'))
        total = float(df['amount'].sum())
        # compute this-month total safely
        if not df['date'].isna().all():
            latest_period = df['date'].dt.to_period('M').max()
            month_total = float(df[df['date'].dt.to_period('M') == latest_period]['amount'].sum())
        else:
            month_total = 0.0
    else:
        df = pd.DataFrame()
        total = 0.0
        month_total = 0.0

    # pass dictionary rows to template (templates work with mapping)
    return render_template("index.html", expenses=rows_list, total=total, month_total=month_total)

@app.route("/add", methods=("GET", "POST"))
def add():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title or not amount or not date:
            flash("Title, amount and date are required.", "danger")
            return redirect(url_for("add"))
        try:
            amount_val = float(amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return redirect(url_for("add"))
        try:
            parsed = datetime.fromisoformat(date)
            date_str = parsed.date().isoformat()
        except Exception:
            flash("Date format should be YYYY-MM-DD.", "danger")
            return redirect(url_for("add"))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO expenses (title, amount, category, date, notes) VALUES (?, ?, ?, ?, ?)",
                    (title, amount_val, category, date_str, notes))
        conn.commit()
        conn.close()
        flash("Expense added successfully.", "success")
        return redirect(url_for("index"))

    today = datetime.today().date().isoformat()
    return render_template("add.html", today=today)

@app.route("/edit/<int:expense_id>", methods=("GET", "POST"))
def edit(expense_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
    expense = cur.fetchone()
    if expense is None:
        conn.close()
        flash("Expense not found.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title or not amount or not date:
            flash("Title, amount and date are required.", "danger")
            return redirect(url_for("edit", expense_id=expense_id))
        try:
            amount_val = float(amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return redirect(url_for("edit", expense_id=expense_id))
        try:
            parsed = datetime.fromisoformat(date)
            date_str = parsed.date().isoformat()
        except Exception:
            flash("Date format should be YYYY-MM-DD.", "danger")
            return redirect(url_for("edit", expense_id=expense_id))

        cur.execute("""UPDATE expenses
                       SET title = ?, amount = ?, category = ?, date = ?, notes = ?
                       WHERE id = ?""",
                    (title, amount_val, category, date_str, notes, expense_id))
        conn.commit()
        conn.close()
        flash("Expense updated.", "success")
        return redirect(url_for("index"))

    conn.close()
    return render_template("edit.html", expense=expense)

@app.route("/delete/<int:expense_id>", methods=("POST",))
def delete(expense_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    flash("Expense deleted.", "info")
    return redirect(url_for("index"))

@app.route("/export")
def export_csv():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, amount, category, date, notes FROM expenses ORDER BY date DESC")
    rows = cur.fetchall()
    conn.close()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "title", "amount", "category", "date", "notes"])
    for r in rows:
        cw.writerow([r["id"], r["title"], r["amount"], r["category"], r["date"], r["notes"]])
    output = io.BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="expenses.csv")

if __name__ == "__main__":
    if not DB_PATH.exists():
        import db_init
        db_init.init_db()
    app.run(debug=True)
