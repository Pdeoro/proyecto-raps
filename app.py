from flask import Flask, render_template, request, redirect, session
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "raps_secret_key"

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="raps_db"
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        username = request.form["username"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password, username) VALUES (%s, %s, %s)", (email, password, username))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/login")
    return render_template("registro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["username"] = user["username"]
            session["foto"] = user["foto"]
            return redirect("/")
        else:
            return render_template("login.html", error="Correo o contraseña incorrectos")

    return render_template("login.html")

@app.route("/foro", methods=["GET", "POST"])
def foro():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        content = request.form["content"]
        user_id = session.get("user_id")
        if user_id:
            cursor.execute("INSERT INTO posts (content, user_id) VALUES (%s, %s)", (content, user_id))
            conn.commit()

    cursor.execute("""
        SELECT posts.*, users.username,
        (SELECT COUNT(*) FROM likes_posts WHERE likes_posts.post_id = posts.id) as total_likes
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.id DESC
    """)
    posts = cursor.fetchall()

    for post in posts:
        cursor.execute("""
            SELECT comentarios.*, users.username 
            FROM comentarios 
            JOIN users ON comentarios.user_id = users.id 
            WHERE comentarios.post_id = %s 
            ORDER BY comentarios.created_at ASC
        """, (post["id"],))
        post["comentarios"] = cursor.fetchall()

        if session.get("user_id"):
            cursor.execute("SELECT * FROM likes_posts WHERE post_id=%s AND user_id=%s", (post["id"], session.get("user_id")))
            post["user_liked"] = cursor.fetchone() is not None
        else:
            post["user_liked"] = False

    cursor.close()
    conn.close()

    return render_template("foro.html", posts=posts)

@app.route("/recursos")
def recursos():
    return render_template("recursos.html")

@app.route("/tests")
def tests():
    return render_template("tests.html")

@app.route("/info")
def info():
    return render_template("info.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/like/<int:post_id>", methods=["POST"])
def like_post(post_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM likes_posts WHERE post_id=%s AND user_id=%s", (post_id, user_id))
    like_existente = cursor.fetchone()

    if like_existente:
        cursor.execute("DELETE FROM likes_posts WHERE post_id=%s AND user_id=%s", (post_id, user_id))
    else:
        cursor.execute("INSERT INTO likes_posts (post_id, user_id) VALUES (%s, %s)", (post_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/foro")

@app.route("/comentar/<int:post_id>", methods=["POST"])
def comentar(post_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    contenido = request.form.get("contenido")
    if contenido:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comentarios (post_id, user_id, contenido) VALUES (%s, %s, %s)", (post_id, user_id, contenido))
        conn.commit()
        cursor.close()
        conn.close()

    return redirect("/foro")

@app.route("/perfil")
def perfil():
    if not session.get("user_id"):
        return redirect("/login")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    usuario = cursor.fetchone()

    cursor.execute("""
        SELECT posts.*, 
        (SELECT COUNT(*) FROM likes_posts WHERE likes_posts.post_id = posts.id) as total_likes,
        (SELECT COUNT(*) FROM comentarios WHERE comentarios.post_id = posts.id) as total_comentarios
        FROM posts 
        WHERE posts.user_id = %s 
        ORDER BY posts.id DESC
    """, (session["user_id"],))
    mis_posts = cursor.fetchall()

    cursor.close()
    conn.close()

    session["foto"] = usuario["foto"]

    return render_template("perfil.html", usuario=usuario, mis_posts=mis_posts)

@app.route("/actualizar_foto", methods=["POST"])
def actualizar_foto():
    if not session.get("user_id"):
        return redirect("/login")

    if 'foto' not in request.files:
        return redirect("/perfil")

    file = request.files['foto']

    if file and allowed_file(file.filename):
        filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET foto=%s WHERE id=%s", (filename, session["user_id"]))
        conn.commit()
        cursor.close()
        conn.close()

        session["foto"] = filename

    return redirect("/perfil")

if __name__ == "__main__":
    app.run(debug=True)