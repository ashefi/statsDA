import streamlit as st
import pandas as pd
import re
from nba_api.live.nba.endpoints import scoreboard, boxscore, playbyplay
from nba_api.stats.endpoints import playergamelog, playbyplayv2
from nba_api.stats.static import players

# --- הגדרות עיצוב ---
st.set_page_config(page_title="Deni Stats", page_icon="🏀")
st.title("🏀 Deni Avdija Tracker")

# --- פונקציות עזר ---

@st.cache_data
def get_player_info():
    # החזרת גם ID וגם השם המלא לחיפוש טקסטואלי
    p = players.find_players_by_full_name("Deni Avdija")
    return p[0] if p else None

def parse_time_string(time_str):
    # המרת זמן שעון לדקה במשחק
    try:
        time_s = str(time_str)
        if "PT" in time_s: # פורמט לייב PT12M
            match = re.search(r'PT(\d+)M(\d+)\.', time_s)
            if match:
                return 12 - (int(match.group(1)) + int(match.group(2))/60)
        elif ":" in time_s: # פורמט היסטורי 10:45
            parts = time_s.split(':')
            if len(parts) == 2:
                mins, secs = map(int, parts)
                return 12 - (mins + secs/60)
    except:
        pass
    return 0

def generate_chart_data(game_id, player_id, player_name="Avdija", is_live=False):
    chart_data = [{"Minute": 0, "Points": 0}]
    running_score = 0
    found_events = False
    
    try:
        # ניסיון 1: נתונים היסטוריים (PlayByPlayV2)
        # זה עובד לרוב המשחקים שכבר נגמרו
        df_pbp = playbyplayv2.PlayByPlayV2(game_id).get_data_frames()[0]
        
        # חיפוש גמיש: או לפי ID או לפי השם במשפחה בתיאור
        for i, row in df_pbp.iterrows():
            desc = str(row['HOMEDESCRIPTION']) + " " + str(row['VISITORDESCRIPTION'])
            
            # בדיקה אם זה מהלך של דני
            is_deni = (str(player_id) in str(row['PLAYER1_ID'])) or (player_name in desc)
            
            # בדיקה אם נכנס סל (לא החטאה)
            # EVENTMSGTYPE: 1=סל, 3=עונשין
            is_score = row['EVENTMSGTYPE'] == 1 or (row['EVENTMSGTYPE'] == 3 and "MISS" not in desc)
            
            if is_deni and is_score:
                points = 0
                if "3PT" in desc: points = 3
                elif "Free Throw" in desc: points = 1
                else: points = 2 # ברירת מחדל לסל רגיל
                
                # זמן
                period = row['PERIOD']
                minutes_passed = ((period - 1) * 12) + parse_time_string(row['PCTIMESTRING'])
                
                running_score += points
                chart_data.append({"Minute": minutes_passed, "Points": running_score})
                found_events = True

    except Exception as e:
        # אם נכשל, ננסה את ה-API של הלייב (לפעמים עובד גם לישנים)
        pass

    # אם לא מצאנו כלום בשיטה הראשונה, ננסה שיטה שנייה (Live Endpoint)
    if not found_events:
        try:
            pbp = playbyplay.PlayByPlay(game_id).get_dict()
            actions = pbp['game']['actions']
            for action in actions:
                if action['personId'] == player_id and action['isScore'] == 1:
                    period = action['period']
                    minutes_passed = ((period - 1) * 12) + parse_time_string(action['clock'])
                    
                    # זיהוי נקודות
                    desc = action['description']
                    points = 2
                    if "Free Throw" in desc: points = 1
                    elif "3pt Shot" in desc: points = 3
                    
                    running_score += points
                    chart_data.append({"Minute": minutes_passed, "Points": running_score})
        except:
            pass
            
    return pd.DataFrame(chart_data)

# --- לוגיקה ראשית ---

player_info = get_player_info()
if not player_info:
    st.error("Player not found!")
    st.stop()

deni_id = player_info['id']
deni_name = "Avdija" # שם לחיפוש בטקסט

# בדיקת משחקים חיים
board = scoreboard.ScoreBoard()
games = board.games.get_dict()
live_game_found = False

st.write("Checking status...")

# 1. ניסיון למצוא משחק חי
for game in games:
    if game['gameStatus'] == 2: # משחק פעיל
        try:
            box = boxscore.BoxScore(game_id=game['gameId']).game.get_dict()
            all_players = box['homeTeam']['players'] + box['awayTeam']['players']
            
            for p in all_players:
                if p['personId'] == deni_id:
                    live_game_found = True
                    st.success(f"🔴 LIVE: {box['awayTeam']['teamName']} vs {box['homeTeam']['teamName']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Points", p['statistics']['points'])
                    c2.metric("Rebounds", p['statistics']['reboundsTotal'])
                    c3.metric("Assists", p['statistics']['assists'])
                    
                    st.subheader("📈 Scoring Timeline")
                    df_chart = generate_chart_data(game['gameId'], deni_id, deni_name)
                    if len(df_chart) > 1:
                        st.line_chart(df_chart, x="Minute", y="Points")
                    else:
                        st.info("Game started, waiting for first points...")
                    break
        except:
            continue

# 2. אם אין משחק חי - היסטוריה + גרף
if not live_game_found:
    try:
        gamelog = playergamelog.PlayerGameLog(player_id=deni_id)
        df = gamelog.get_data_frames()[0]
        
        if not df.empty:
            last_game = df.iloc[0]
            game_id = last_game['Game_ID']
            
            # תיקון תאריך - הצגה יפה
            st.info(f"Last Game: {last_game['GAME_DATE']}")
            st.caption(f"{last_game['MATCHUP']} | {last_game['WL']}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Points", last_game['PTS'])
            c2.metric("Rebounds", last_game['REB'])
            c3.metric("Assists", last_game['AST'])
            
            # טבלה נקייה
            st.dataframe(pd.DataFrame({
                'Steals': [last_game['STL']],
                'Blocks': [last_game['BLK']],
                'Minutes': [last_game['MIN']]
            }), hide_index=True)
            
            # גרף
            st.subheader("📈 Scoring Timeline (Last Game)")
            
            # נסה למשוך גרף
            df_chart = generate_chart_data(game_id, deni_id, deni_name)
            
            if len(df_chart) > 1: # אם יש יותר מנקודה אחת (0,0)
                st.line_chart(df_chart, x="Minute", y="Points")
            else:
                st.warning(f"Could not load play-by-play data for Game ID {game_id}.")
                # אופציה לדיבוג: נראה למשתמש אם ה-ID נראה תקין
                # st.write(f"Debug info: GameID used: {game_id}")
            
        else:
            st.write("No games found for this season yet.")
            
    except Exception as e:
        st.error(f"Could not load history: {e}")

if st.button('Refresh'):
    st.rerun()
