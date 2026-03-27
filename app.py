# app.py — Tap2Drop бот (полностью исправленная версия)
from flask import Flask, request, jsonify
import telebot
import json
import os
import time
import math
import random

app = Flask(__name__)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8511088817:AAFy8t4LALPR5jPl0vANi_HLREd2JQ2nCFY")
DATA_FILE = "tap2drop_data.json"

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
    
    if player["energy"] <= 0:
        return {"success": False, "error": "⚡ Нет энергии! Подождите 5 минут."}
    
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
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Tap2Drop — Тапай и зарабатывай!</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; user-select: none; -webkit-tap-highlight-color: transparent; }
        body {
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 100%);
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: white;
            padding: 20px;
            padding-bottom: 80px;
        }
        .header {
            background: rgba(0,0,0,0.4);
            border-radius: 24px;
            padding: 16px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .stats {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 15px;
        }
        .stat {
            flex: 1;
            text-align: center;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 8px;
        }
        .stat-label { font-size: 11px; opacity: 0.7; }
        .stat-value { font-size: 18px; font-weight: bold; }
        .burn-value { color: #ff6666; }
        .tap-area { display: flex; justify-content: center; margin: 20px 0; }
        .tap-button {
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: linear-gradient(135deg, #ffd700, #ff6600);
            box-shadow: 0 20px 30px rgba(0,0,0,0.4), inset 0 2px 10px rgba(255,255,255,0.3);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.08s ease;
        }
        .tap-button:active { transform: scale(0.95); }
        .tap-icon { font-size: 64px; }
        .tap-text { font-size: 24px; font-weight: bold; margin-top: 8px; }
        .energy-bar {
            background: #333;
            border-radius: 10px;
            height: 10px;
            overflow: hidden;
            margin: 15px 0;
        }
        .energy-fill {
            background: linear-gradient(90deg, #00ff00, #ffff00);
            height: 100%;
            transition: width 0.3s;
        }
        .combo {
            text-align: center;
            margin: 15px 0;
            font-size: 18px;
            font-weight: bold;
            color: #ff6600;
            min-height: 45px;
        }
        .progress-bar {
            background: #333;
            border-radius: 10px;
            height: 6px;
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
            gap: 12px;
            margin: 20px 0;
        }
        .game-card {
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .game-card:active { transform: scale(0.95); }
        .game-icon { font-size: 32px; margin-bottom: 6px; }
        .game-name { font-size: 11px; }
        .game-reward { font-size: 10px; color: #ffd700; }
        .nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.95);
            display: flex;
            justify-content: space-around;
            padding: 12px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .nav-btn {
            background: none;
            border: none;
            color: #888;
            font-size: 12px;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .nav-btn.active { color: #ffd700; background: rgba(255,215,0,0.2); }
        .particle {
            position: fixed;
            pointer-events: none;
            font-size: 14px;
            font-weight: bold;
            animation: floatUp 0.5s ease-out forwards;
            z-index: 1000;
        }
        @keyframes floatUp {
            0% { opacity: 1; transform: translateY(0) scale(1); }
            100% { opacity: 0; transform: translateY(-50px) scale(1.2); }
        }
        .profile-card {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 16px;
            margin: 15px 0;
            text-align: left;
        }
        .profile-card p { margin: 8px 0; }
        .referral-code {
            background: rgba(0,0,0,0.5);
            padding: 10px;
            border-radius: 10px;
            word-break: break-all;
            font-family: monospace;
            font-size: 12px;
            text-align: center;
        }
        .achievement {
            background: rgba(255,215,0,0.1);
            padding: 8px;
            border-radius: 10px;
            margin: 5px 0;
            font-size: 12px;
        }
        .error-container {
            text-align: center;
            padding: 50px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .error-container button {
            margin-top: 20px;
            padding: 12px 24px;
            background: #ffd700;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            cursor: pointer;
            color: #000;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="stats">
            <div class="stat">
                <div class="stat-label">💰</div>
                <div class="stat-value" id="tokens">0</div>
            </div>
            <div class="stat">
                <div class="stat-label">⚡</div>
                <div class="stat-value" id="energy">100</div>
            </div>
            <div class="stat">
                <div class="stat-label">📉</div>
                <div class="stat-value" id="emission">0</div>
            </div>
            <div class="stat">
                <div class="stat-label">🔥</div>
                <div class="stat-value burn-value" id="burned">0</div>
            </div>
        </div>
        <div class="energy-bar">
            <div class="energy-fill" id="energyFill"></div>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        <div style="font-size:12px; text-align:center;">🎯 <span id="progressText">0</span>% до аирдропа</div>
    </div>
    
    <div class="tap-area">
        <div class="tap-button" id="tapBtn">
            <div class="tap-icon">🖱️</div>
            <div class="tap-text">ТАП</div>
            <div id="tapValue" style="font-size:12px;">+0.00</div>
            <div id="burnValue" style="font-size:10px; color:#ff8888;">🔥 0.00 сгорает</div>
        </div>
    </div>
    
    <div class="combo" id="combo"></div>
    
    <div id="gamesPanel" style="display:none;">
        <h3 style="margin: 15px 0 10px;">🎮 Мини-игры</h3>
        <div class="games-grid">
            <div class="game-card" onclick="playGame('match')">
                <div class="game-icon">🃏</div>
                <div class="game-name">Мем-матч</div>
                <div class="game-reward">+10-60⚡</div>
            </div>
            <div class="game-card" onclick="playGame('quiz')">
                <div class="game-icon">📚</div>
                <div class="game-name">Викторина</div>
                <div class="game-reward">+30-50⚡</div>
            </div>
            <div class="game-card" onclick="playGame('slot')">
                <div class="game-icon">🎰</div>
                <div class="game-name">Слоты</div>
                <div class="game-reward">+5-100⚡</div>
            </div>
        </div>
    </div>
    
    <div id="profilePanel" style="display:none;">
        <div id="profileInfo" class="profile-card"></div>
        <div id="referralLink"></div>
        <div id="achievements"></div>
    </div>
    
    <div class="nav">
        <button class="nav-btn active" data-tab="tap">🖱️ Тап</button>
        <button class="nav-btn" data-tab="games">🎮 Игры</button>
        <button class="nav-btn" data-tab="profile">👤 Профиль</button>
    </div>
    
    <script>
        let userId = null;
        let tg = window.Telegram?.WebApp;
        
        // Получаем ID пользователя из Telegram WebApp
        if (tg) {
            tg.expand();
            tg.ready();
            userId = tg.initDataUnsafe?.user?.id;
            console.log("Telegram WebApp detected, User ID:", userId);
        }
        
        // Если нет user ID — показываем инструкцию
        if (!userId) {
            document.body.innerHTML = `
                <div class="error-container" style="background: linear-gradient(135deg, #0a0a1a, #1a1a2e); min-height: 100vh; color: white;">
                    <h2>❌ Ошибка</h2>
                    <p style="margin: 20px 0;">Не удалось определить пользователя.</p>
                    <p>Пожалуйста, откройте это приложение <strong>ТОЛЬКО через кнопку в Telegram боте</strong>.</p>
                    <p style="margin: 20px 0;">👇 Нажмите кнопку "🚀 ИГРАТЬ" в боте</p>
                    <button onclick="window.location.href='https://t.me/Tap2Drop_official_bot'">
                        🔙 Открыть бота
                    </button>
                </div>
            `;
            throw new Error("No user ID");
        }
        
        // Загрузка данных пользователя
        async function loadData() {
            if (!userId) return;
            try {
                let resp = await fetch('/api/user/' + userId);
                let data = await resp.json();
                if (data.success) {
                    document.getElementById('tokens').innerText = Math.floor(data.tokens).toLocaleString();
                    document.getElementById('energy').innerText = data.energy;
                    document.getElementById('emission').innerText = data.emission_rate?.toFixed(2) || '0';
                    document.getElementById('energyFill').style.width = (data.energy / 100 * 100) + '%';
                    document.getElementById('progressFill').style.width = (data.progress || 0) + '%';
                    document.getElementById('progressText').innerText = data.progress?.toFixed(2) || '0';
                }
            } catch(e) {
                console.error("Load error:", e);
            }
        }
        
        // Обработка тапа
        document.getElementById('tapBtn').onclick = async () => {
            if (!userId) return;
            let btn = document.getElementById('tapBtn');
            btn.style.transform = 'scale(0.95)';
            setTimeout(() => btn.style.transform = '', 100);
            
            try {
                let resp = await fetch('/api/tap', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId})
                });
                let data = await resp.json();
                if (data.success) {
                    document.getElementById('tokens').innerText = Math.floor(data.tokens).toLocaleString();
                    document.getElementById('energy').innerText = data.energy;
                    document.getElementById('tapValue').innerHTML = `+${data.earned.toFixed(4)}`;
                    document.getElementById('burnValue').innerHTML = `🔥 ${data.burned.toFixed(4)} сгорает`;
                    document.getElementById('energyFill').style.width = (data.energy / 100 * 100) + '%';
                    
                    if (data.combo > 1) {
                        document.getElementById('combo').innerHTML = `🔥 x${data.combo} COMBO! +${data.bonus_percent.toFixed(0)}%`;
                    } else {
                        document.getElementById('combo').innerHTML = '';
                    }
                    
                    let particle = document.createElement('div');
                    particle.className = 'particle';
                    particle.innerHTML = `+${data.earned.toFixed(4)}`;
                    particle.style.left = Math.random() * window.innerWidth + 'px';
                    particle.style.top = window.innerHeight - 150 + 'px';
                    document.body.appendChild(particle);
                    setTimeout(() => particle.remove(), 500);
                } else if (data.error) {
                    alert(data.error);
                }
            } catch(e) {
                console.error("Tap error:", e);
                alert("Ошибка соединения. Проверьте интернет.");
            }
        };
        
        // Мини-игры
        async function playGame(game) {
            if (!userId) return;
            try {
                let resp = await fetch('/api/play_game', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, game: game})
                });
                let data = await resp.json();
                if (data.success) {
                    alert(`🎮 Игра завершена! +${data.energy_gain} ⚡ энергии`);
                    document.getElementById('energy').innerText = data.new_energy;
                    document.getElementById('energyFill').style.width = (data.new_energy / 100 * 100) + '%';
                } else {
                    alert(data.error);
                }
            } catch(e) {
                alert("Ошибка игры");
            }
        }
        
        // Загрузка профиля
        async function loadProfile() {
            if (!userId) return;
            try {
                let resp = await fetch('/api/user/' + userId);
                let data = await resp.json();
                if (data.success) {
                    document.getElementById('profileInfo').innerHTML = `
                        <p>👤 ${data.username}</p>
                        <p>📊 Тапов: ${data.total_taps?.toLocaleString() || 0}</p>
                        <p>💰 Токенов: ${Math.floor(data.tokens).toLocaleString()} $T2D</p>
                        <p>⚡ Энергии: ${data.energy}/100</p>
                    `;
                    
                    let botUsername = "Tap2Drop_official_bot";
                    document.getElementById('referralLink').innerHTML = `
                        <h4>👥 Реферальная ссылка</h4>
                        <div class="referral-code">https://t.me/${botUsername}?start=ref_${userId}</div>
                        <p style="font-size:11px; margin-top:8px;">Приведи друга → получи 10% от его токенов!</p>
                    `;
                    
                    let achievementsHtml = '<h4>🏆 Достижения</h4>';
                    if (data.total_taps >= 1000) achievementsHtml += '<div class="achievement">🥉 Бронзовый палец (1000 тапов)</div>';
                    if (data.total_taps >= 10000) achievementsHtml += '<div class="achievement">🥈 Серебряный палец (10000 тапов)</div>';
                    if (data.total_taps >= 100000) achievementsHtml += '<div class="achievement">🥇 Золотой палец (100000 тапов)</div>';
                    if (data.total_taps >= 1000000) achievementsHtml += '<div class="achievement">💎 Алмазный палец (1M тапов)</div>';
                    if (data.total_taps < 1000) achievementsHtml += '<p>Начни тапать, чтобы получить достижения!</p>';
                    document.getElementById('achievements').innerHTML = achievementsHtml;
                }
            } catch(e) {
                console.error("Profile error:", e);
            }
        }
        
        // Навигация
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                let tab = btn.dataset.tab;
                document.querySelector('.tap-area').style.display = tab === 'tap' ? 'flex' : 'none';
                document.getElementById('gamesPanel').style.display = tab === 'games' ? 'block' : 'none';
                document.getElementById('profilePanel').style.display = tab === 'profile' ? 'block' : 'none';
                if (tab === 'profile') loadProfile();
            };
        });
        
        // Запуск
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
    active = get_active_users(data)
    
    return jsonify({
        "success": True,
        "username": player["username"],
        "tokens": player["tokens"],
        "energy": player["energy"],
        "total_taps": player["total_taps"],
        "emission_rate": get_emission_rate(active),
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
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Webhook error: {e}")
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
    
    webapp_url = os.environ.get("RENDER_EXTERNAL_URL", "https://t2d-official.onrender.com")
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
        f"👇 *Нажми ИГРАТЬ!*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

application = app
