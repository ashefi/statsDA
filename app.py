import streamlit as st
import pandas as pd
import requests
import re
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players
from nba_api.live.nba.endpoints import scoreboard, boxscore

# --- הגדרות עיצוב ---
st.set_page_config(page_title="Deni Stats", page_icon="🏀")
st.title("🏀 Deni Avdija Tracker")

# --- פונקציות עזר (משופרות עם כותרות) ---

def get_json_with_headers(url):
    # פונקציה שמושכת מידע עם "תחפושת" של דפדפן כדי למנוע חסימות
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

@st.cache_data
def get_player_info():
    try:
        p = players.find_players_by_full_name("Deni Avdija")
        return p[0] if p else None
    except:
        return None

def parse_time(time_str):
    # ממיר זמן (PT10M או 10:00) לדקות שנותרו ברבע
    try:
        ts = str(time_str)
        if "PT" in ts: # פורמט לייב
            match = re.search(r'PT(\d+)M(\d+)\.', ts)
            if match:
                return int(match.group(1)) + int(match.group(2))/60
        elif ":" in ts: # פורמט היסטורי
            parts = ts.split(':')
            return int(parts[0]) + int(parts[1])/60
    except:
        pass
    return 12.0 # ברירת מחדל

def get_chart_data(game_id, player_id):
    # מנסה למשוך נתונים בשתי שיטות: לייב והיסטוריה
    chart_data = [{"Minute": 0, "Points": 0}]
    running_score = 0
    found = False

    # שיטה 1: API של לייב (עובד הכי טוב לגרפים)
    url_live = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
    data = get_json_with_headers(url_live)
    
    if data and 'game' in data and 'actions' in data['game']:
        actions = data['game']['actions']
        for action in actions:
            if action['isScore'] == 1 and action['personId'] == player_id:
                # חישוב זמן במשחק (דקה 0 עד 48)
                period = action['period']
                time_left = parse_time(action['clock'])
                minute_in_game = (period - 1) * 12 + (12 - time_left)
                
                # חישוב נקודות
                pts_type = action['shotResult'] # לרוב מכיל מידע
                desc = action['description']
                points_added = 2
                if "3pt" in desc.lower(): points_added = 3
                elif "free throw" in desc.lower(): points_added = 1
                
                running_score += points_added
                chart_data.append({"Minute": minute_in_game, "Points": running_score})
        found = True

    # שיטה 2: אם שיטה 1 נכשלה (למשחקים ישנים מאוד), ננסה את ה-V2 API ידנית
    if not found:
        url_v2 = f"https://stats.nba.com/stats/playbyplayv2?GameID={game_id}&StartPeriod=0&EndPeriod=14"
        data_v2 = get_json_with_headers(url_v2)
        
        if data_v2 and 'resultSets' in data_v2:
            headers = data_v2['resultSets'][0]['headers']
            rows = data_v2['resultSets'][0]['rowSet']
            
            # מיפוי אינדקסים
            try:
                i_pid = headers.index("PLAYER1_ID")
                i_desc = headers.index("HOMEDESCRIPTION")
                i_visit_desc = headers.index("VISITORDESCRIPTION")
                i_period = headers.index("PERIOD")
                i_clock = headers.index("PCTIMESTRING")
                i_event = headers.index("EVENTMSGTYPE") # 1=סל, 3=עונשין
            except:
                return pd.DataFrame(chart_data)

            for row in rows:
                if row[i_pid] == player_id:
                    event_type = row[i_event]
                    desc = str(row[i_desc]) + str(row[i_visit_desc])
                    
                    is_basket = (event_type == 1)
                    is_ft = (event_type == 3 and "MISS" not in desc)
                    
                    if is_basket or is_ft:
                        points_added = 2
                        if "3PT" in desc: points_added = 3
                        elif is_ft: points_added = 1
                        
                        period = row[i_period]
                        time_left = parse_time(row[i_clock])
                        minute_in_game = (period - 1) * 12 + (12 - time_left)
                        
                        running_score += points_added
                        chart_data.append({"Minute": minute_in_game, "Points": running_score})

    return pd.DataFrame(chart_data)

# --- לוגיקה ראשית ---

player = get_player_info()
if not player:
    st.error("Player not found")
    st.stop()
    
deni_id = player['id']

# בדיקת לייב
board = scoreboard.ScoreBoard()
games_dict = board.games.get_dict()
live_found = False

st.write("Checking data...")

for game in games_dict:
    if game['gameStatus'] == 2:
        try:
            bx = boxscore.BoxScore(game['gameId']).game.get_dict()
            players_list = bx['homeTeam']['players'] + bx['awayTeam']['players']
            for p in players_list:
                if p['personId'] == deni_id:
                    live_found = True
                    st.success(f"🔴 LIVE: {bx['awayTeam']['teamName']} vs {bx['homeTeam']['teamName']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Points", p['statistics']['points'])
                    c2.metric("Rebounds", p['statistics']['reboundsTotal'])
                    c3.metric("Assists", p['statistics']['assists'])
                    
                    st.subheader("📈 Game Flow")
                    df = get_chart_data(game['gameId'], deni_id)
                    st.line_chart(df, x="Minute", y="Points")
                    break
        except: pass

if not live_found:
    try:
        # שליפת משחק אחרון
        log = playergamelog.PlayerGameLog(player_id=deni_id)
        df_log = log.get_data_frames()[0]
        
        if not df_log.empty:
            last = df_log.iloc[0]
            gid = last['Game_ID']
            
            st.info(f"Last Game: {last['GAME_DATE']}")
            st.caption(f"{last['MATCHUP']} | {last['WL']}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Points", last['PTS'])
            c2.metric("Rebounds", last['REB'])
            c3.metric("Assists", last['AST'])
            
            st.subheader("📈 Game Flow")
            with st.spinner("Loading chart..."):
                df_chart = get_chart_data(gid, deni_id)
                if len(df_chart) > 1:
                    st.line_chart(df_chart, x="Minute", y="Points")
                else:
                    st.warning(f"Could not load chart data for Game ID {gid}")
                    
            st.dataframe(pd.DataFrame({
                'Min': [last['MIN']],
                'FG': [f"{last['FGM']}/{last['FGA']}"],
                '3PT': [f"{last['FG3M']}/{last['FG3A']}"]
            }), hide_index=True)
            
        else:
            st.write("No games found.")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("Refresh"):
    st.rerun()
