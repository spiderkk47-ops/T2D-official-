# app.py — Tap2Drop бот
from flask import Flask, request, jsonify, render_template_string
import telebot
import json
import os
import time
import math
import random
import requests

app = Flask(__name__)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8511088817:AAFy8t4LALPR5jPl0vANi_HLREd2JQ2nCFY")
DATA_FILE = "tap2drop_data.json"

# Параметры токеномики
PLAYER_POOL = 60_000_000_000
BURN_PERCENT = 0.10
MIN_EMISSION = 0.5
START_BONUS = 500

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "players": {},
        "total_emission": 0,
        "total_burned": 0,
        "total_users": 0,
        "total_taps": 0,
        "airdrop_triggered": False
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_active_users(data):
    now = time.time()
    active = 0
    for p in data["players"].values():
        if now - p.get("last_tap", 0) < 86400:
            active += 1
    return max(active, 1)

def get_emission_rate(active):
    if active < 100:
        return 100.0
    try:
        emission = 100 / (1 + math.log10(active / 100))
    except:
        emission = 100.0
    return max(emission, MIN_EMISSION)

def get_airdrop_info(data):
    if data.get("airdrop_triggered", False):
        return {"progress": 100, "message": "🎉 АИРДРОП ЗАПУЩЕН!"}
    progress = (data["total_emission"] / PLAYER_POOL) * 100
    return {"progress": min(progress, 99.99), "message": f"📊 Прогресс: {progress:.2f}%"}

def process_tap(user_id):
    data = load_data()
    uid = str(user_id)
    
    if data.get("airdrop_triggered", False):
        return {"success": False, "error": "❌ Аирдроп уже запущен!"}
    
    if uid not in data["players"]:
        return {"success": False, "error": "User not found"}
    
    player = data["players"][uid]
    
    if player["energy"] <= 0:
        return {"success": False, "error": "⚡ Нет энергии!"}
    
    now = time.time()
    
    if now - player.get("last_tap", 0) < 1.0:
        player["combo"] = min(player.get("combo", 0) + 1, 100)
    else:
        player["combo"] = 1
    
    active = get_active_users(data)
    emission_rate = get_emission_rate(active)
    combo_bonus = min(player["combo"] * 0.02, 2.0)
    total = emission_rate * (1 + combo_bonus)
    
    burned = total * BURN_PERCENT
    player_gain = total - burned
    
    player["energy"] -= 1
    player["total_taps"] = player.get("total_taps", 0) + 1
    player["tokens"] = player.get("tokens", 0) + player_gain
    player["last_tap"] = now
    
    data["total_emission"] = data.get("total_emission", 0) + total
    data["total_burned"] = data.get("total_burned", 0) + burned
    data["total_taps"] = data.get("total_taps", 0) + 1
    
    save_data(data)
    
    if data["total_emission"] >= PLAYER_POOL and not data.get("airdrop_triggered"):
        data["airdrop_triggered"] = True
        save_data(data)
    
    return {
        "success": True,
        "earned": player_gain,
        "burned": burned,
        "tokens": player["tokens"],
        "energy": player["energy"],
        "combo": player["combo"],
        "bonus_percent": combo_bonus * 100,
        "emission_rate": emission_rate
    }

# ==================== HTML MINI APP ====================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tap2Drop</title>
    <style>
        * { user-select: none; -webkit-tap-highlight-color: transparent; }
        body {
            background: linear-gradient(135deg, #0a0a1a, #1a1a2e);
            color: white;
            font-family: Arial;
            text-align: center;
            padding: 20px;
            min-height: 100vh;
        }
        .tap-btn {
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ffd700, #ff6600);
            margin: 30px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 64px;
            cursor: pointer;
            transition: transform 0.08s;
            box-shadow: 0 20px 30px rgba(0,0,0,0.4);
        }
        .tap-btn:active { transform: scale(0.95); }
        .stats {
            background: rgba(0,0,0,0.4);
            padding: 15px;
            border-radius: 20px;
            margin: 20px 0;
        }
        .energy-bar {
            background: #333;
            height: 10px;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .energy-fill {
            background: linear-gradient(90deg, #00ff00, #ffff00);
            height: 100%;
            transition: width 0.3s;
        }
        .combo { color: #ff6600; margin: 10px 0; font-size: 18px; }
        .nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.95);
            display: flex;
            padding: 12px;
            gap: 10px;
            justify-content: center;
        }
        .nav-btn {
            background: none;
            border: none;
            color: #888;
            padding: 8px 20px;
            border-radius: 20px;
            cursor: pointer;
        }
        .nav-btn.active { color: #ffd700; background: rgba(255,215,0,0.2); }
        .progress-bar {
            background: #333;
            height: 6px;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            background: linear-gradient(90deg, #ff4444, #ffaa00);
            height: 100%;
            transition: width 0.3s;
        }
        .games-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin: 20px 0;
        }
        .game-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 12px;
            cursor: pointer;
        }
        .game-card:active { transform: scale(0.95); }
        .particle {
            position: fixed;
            pointer-events: none;
            font-size: 14px;
            color: gold;
            animation: floatUp 0.5s forwards;
            z-index: 1000;
        }
        @keyframes floatUp {
            0% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(-50px); }
        }
    </style>
</head>
<body>
    <h1>🔥 Tap2Drop</h1>
    <div class="stats">
        <div>💰 <span id="tokens">0</span> $T2D</div>
        <div>⚡ <span id="energy">100</span>/100</div>
        <div class="energy-bar"><div class="energy-fill" id="energyFill"></div></div>
        <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
        <div>🎯 <span id="progressText">0</span>% до аирдропа</div>
    </div>
    
    <div class="tap-btn" id="tapBtn">🖱️</div>
    <div>+<span id="tapValue">0.00</span> $T2D</div>
    <div class="combo" id="combo"></div>
    
    <div id="gamesPanel" style="display:none;">
        <div class="games-grid">
            <div class="game-card" onclick="playGame('match')">🃏<br>Мем-матч<br><small>+10-60⚡</small></div>
            <div class="game-card" onclick="playGame('quiz')">📚<br>Викторина<br><small>+30-50⚡</small></div>
            <div class="game-card" onclick="playGame('slot')">🎰<br>Слоты<br><small>+5-100⚡</small></div>
        </div>
    </div>
    
    <div id="profilePanel" style="display:none;">
        <div id="profileInfo"></div>
        <div id="referralLink"></div>
    </div>
    
    <div class="nav">
        <button class="nav-btn active" data-tab="tap">🖱️ Тап</button>
        <button class="nav-btn" data-tab="games">🎮 Игры</button>
        <button class="nav-btn" data-tab="profile">👤 Профиль</button>
    </div>
    
    <script>
        let userId = null;
        let tg = window.Telegram?.WebApp;
        if (tg) { tg.expand(); tg.ready(); userId = tg.initDataUnsafe?.user?.id; }
        
        async function loadData() {
            if (!userId) return;
            let r = await fetch('/api/user/' + userId);
            let d = await r.json();
            if (d.success) {
                document.getElementById('tokens').innerText = Math.floor(d.tokens);
                document.getElementById('energy').innerText = d.energy;
                document.getElementById('energyFill').style.width = (d.energy / 100 * 100) + '%';
                document.getElementById('progressFill').style.width = (d.progress || 0) + '%';
                document.getElementById('progressText').innerText = d.progress?.toFixed(2) || '0';
            }
        }
        
        document.getElementById('tapBtn').onclick = async () => {
            if (!userId) return;
            let btn = document.getElementById('tapBtn');
            btn.style.transform = 'scale(0.95)';
            setTimeout(() => btn.style.transform = '', 100);
            
            let r = await fetch('/api/tap', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({user_id: userId}) });
            let d = await r.json();
            if (d.success) {
                document.getElementById('tokens').innerText = Math.floor(d.tokens);
                document.getElementById('energy').innerText = d.energy;
                document.getElementById('tapValue').innerText = d.earned.toFixed(4);
                document.getElementById('energyFill').style.width = (d.energy / 100 * 100) + '%';
                if (d.combo > 1) document.getElementById('combo').innerHTML = `🔥 x${d.combo} COMBO! +${d.bonus_percent.toFixed(0)}%`;
                else document.getElementById('combo').innerHTML = '';
                
                let p = document.createElement('div'); p.className = 'particle';
                p.innerHTML = `+${d.earned.toFixed(4)}`;
                p.style.left = Math.random() * window.innerWidth + 'px';
                p.style.top = window.innerHeight - 150 + 'px';
                document.body.appendChild(p);
                setTimeout(() => p.remove(), 500);
            }
        };
        
        async function playGame(game) {
            let r = await fetch('/api/play_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({user_id: userId, game: game}) });
            let d = await r.json();
            if (d.success) {
                alert(`🎮 Игра завершена! +${d.energy_gain} ⚡`);
                document.getElementById('energy').innerText = d.new_energy;
                document.getElementById('energyFill').style.width = (d.new_energy / 100 * 100) + '%';
            }
        }
        
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                let tab = btn.dataset.tab;
                document.getElementById('tapBtn').style.display = tab === 'tap' ? 'flex' : 'none';
                document.getElementById('gamesPanel').style.display = tab === 'games' ? 'block' : 'none';
                document.getElementById('profilePanel').style.display = tab === 'profile' ? 'block' : 'none';
                if (tab === 'profile') loadProfile();
            };
        });
        
        async function loadProfile() {
            if (!userId) return;
            let r = await fetch('/api/user/' + userId);
            let d = await r.json();
            if (d.success) {
                document.getElementById('profileInfo').innerHTML = `
                    <div style="background:rgba(255,255,255,0.1); padding:15px; border-radius:15px;">
                        <p>👤 ${d.username}</p>
                        <p>📊 Тапов: ${d.total_taps}</p>
                        <p>💰 Токенов: ${Math.floor(d.tokens)} $T2D</p>
                    </div>
                `;
                document.getElementById('referralLink').innerHTML = `
                    <h4>👥 Реферальная ссылка</h4>
                    <code>https://t.me/ВашБот?start=ref_${userId}</code>
                `;
            }
        }
        
        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
"""

# ==================== FLASK API ====================
@app.route('/')
def index():
    return HTML

@app.route('/api/user/<int:user_id>')
def get_user(user_id):
    data = load_data()
    uid = str(user_id)
    
    if uid not in data["players"]:
        data["players"][uid] = {
            "username": f"user_{user_id}",
            "total_taps": 0,
            "tokens": START_BONUS,
            "energy": 100,
            "last_tap": 0,
            "combo": 0
        }
        data["total_users"] += 1
        save_data(data)
    
    player = data["players"][uid]
    airdrop = get_airdrop_info(data)
    
    return jsonify({
        "success": True,
        "username": player["username"],
        "tokens": player["tokens"],
        "energy": player["energy"],
        "total_taps": player["total_taps"],
        "progress": airdrop["progress"]
    })

@app.route('/api/tap', methods=['POST'])
def tap():
    data = request.json
    result = process_tap(data.get("user_id"))
    if result.get("success"):
        airdrop = get_airdrop_info(load_data())
        result["progress"] = airdrop["progress"]
    return jsonify(result)

@app.route('/api/play_game', methods=['POST'])
def play_game_route():
    data = request.json
    user_id = data.get("user_id")
    game = data.get("game")
    
    game_data = load_data()
    uid = str(user_id)
    
    if uid not in game_data["players"]:
        return jsonify({"success": False, "error": "User not found"})
    
    if game == "match":
        gain = random.randint(10, 60)
    elif game == "quiz":
        gain = random.randint(30, 50)
    elif game == "slot":
        gain = random.randint(5, 100)
    else:
        return jsonify({"success": False, "error": "Unknown game"})
    
    game_data["players"][uid]["energy"] = min(game_data["players"][uid]["energy"] + gain, 100)
    save_data(game_data)
    
    return jsonify({
        "success": True,
        "energy_gain": gain,
        "new_energy": game_data["players"][uid]["energy"]
    })

# ==================== TELEGRAM WEBHOOK ====================
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    data = load_data()
    uid = str(user_id)
    
    if uid not in data["players"]:
        data["players"][uid] = {
            "username": username,
            "total_taps": 0,
            "tokens": START_BONUS,
            "energy": 100,
            "last_tap": 0,
            "combo": 0
        }
        data["total_users"] += 1
        save_data(data)
    
    player = data["players"][uid]
    airdrop = get_airdrop_info(data)
    
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(
        text="🚀 ИГРАТЬ",
        web_app=telebot.types.WebAppInfo(url=webapp_url)
    ))
    
    bot.send_message(
        message.chat.id,
        f"🔥 *Tap2Drop*\n\n"
        f"👤 {username}\n"
        f"💰 Токенов: {int(player['tokens'])}\n"
        f"⚡ Энергии: {player['energy']}/100\n"
        f"📊 Тапов: {player['total_taps']}\n\n"
        f"{airdrop['message']}\n\n"
        f"👇 Нажми ИГРАТЬ!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    # Установка вебхука
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_URL', 'localhost')}/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Для Render
application = app
