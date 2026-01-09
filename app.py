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
def get_player_id():
    p = players.find_players_by_full_name("Deni Avdija")
    return p[0]['id'] if p else None

def parse_time_string(time_str):
    # המרת זמן כמו "10:30" או "PT10M30S" למספר דקות שעברו מתחילת הרבע
    # חוזרים עם דקות שנותרו ברבע
    try:
        if "PT" in str(time_str): # פורמט לייב
            match = re.search(r'PT(\d+)M(\d+)\.', str(time_str))
            if match:
                return 12 - (int(match.group(1)) + int(match.group(2))/60)
        elif ":" in str(time_str): # פורמט היסטורי (10:45)
            mins, secs = map(int, str(time_str).split(':'))
            return 12 - (mins + secs/60)
    except:
        pass
    return 0

def generate_chart_data(game_id, player_id, is_live=False):
    # פונקציה חכמה שבונה גרף גם למשחק חי וגם להיסטורי
    chart_data = [{"Minute": 0, "Points": 0}]
    running_score = 0
    
    try:
        if is_live:
            # שימוש ב-API של לייב
            pbp = playbyplay.PlayByPlay(game_id).get_dict()
            actions = pbp['game']['actions']
            for action in actions:
                if action['personId'] == player_id and action['isScore'] == 1:
                    # חישוב זמן
                    period = action['period']
                    minutes_passed = ((period - 1) * 12) + parse_time_string(action['clock'])
                    
                    # חישוב נקודות
                    points = 2
                    desc = action['description']
                    if "Free Throw" in desc: points = 1
                    elif "3pt Shot" in desc: points = 3
                    
                    running_score += points
                    chart_data.append({"Minute": minutes_passed, "Points": running_score})
        else:
            # שימוש ב-API היסטורי (PlayByPlayV2) - עובד למשחקים שנגמרו
            pbp = playbyplayv2.PlayByPlayV2(game_id).get_data_frames()[0]
            # סינון המהלכים של דני שהם סלים
            # EVENTMSGTYPE: 1 = סל שדה, 3 = עונשין
            deni_actions = pbp[((pbp['PLAYER1_ID'] == player_id) & (pbp['EVENTMSGTYPE'].isin([1, 3])))]
            
            for index, row in deni_actions.iterrows():
                # בדיקה אם זו החטאה (ב-V2 לפעמים עונשין מופיע גם כהחטאה תחת סוג 3, אז נבדוק ניקוד)
                # דרך פשוטה יותר: זיהוי לפי תיאור או Score margin אם קיים, אבל נלך על זיהוי סוג זריקה
                
                points = 0
                desc = str(row['HOMEDESCRIPTION']) + str(row['VISITORDESCRIPTION'])
                
                if row['EVENTMSGTYPE'] == 3: # עונשין
                    if "MISS" not in desc: # רק אם לא החטיא
                        points = 1
                elif row['EVENTMSGTYPE'] == 1: # סל שדה
                    points = 3 if "3PT" in desc else 2
                
                if points > 0:
                    period = row['PERIOD']
                    time_str = row['PCTIMESTRING'] # פורמט 10:45
                    minutes_passed = ((period - 1) * 12) + parse_time_string(time_str)
                    
                    running_score += points
                    chart_data.append({"Minute": minutes_passed, "Points": running_score})
                    
        return pd.DataFrame(chart_data)

    except Exception as e:
        print(f"Error generating chart: {e}")
        return pd.DataFrame()

# --- לוגיקה ראשית ---

deni_id = get_player_id()
if not deni_id:
    st.error("Player not found!")
    st.stop()

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
                    
                    # נתונים
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Points", p['statistics']['points'])
                    c2.metric("Rebounds", p['statistics']['reboundsTotal'])
                    c3.metric("Assists", p['statistics']['assists'])
                    st.caption(f"Min: {p['statistics']['minutes']}")

                    # גרף
                    st.subheader("📈 Scoring Timeline")
                    df_chart = generate_chart_data(game['gameId'], deni_id, is_live=True)
                    if not df_chart.empty:
                        st.line_chart(df_chart, x="Minute", y="Points")
                    
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
            
            st.info(f"⚪ Last Game: {last_game['GAME_DATE']}")
            st.caption(f"{last_game['MATCHUP']} | {last_game['WL']}")
            
            # כרטיסי מידע
            c1, c2, c3 = st.columns(3)
            c1.metric("Points", last_game['PTS'])
            c2.metric("Rebounds", last_game['REB'])
            c3.metric("Assists", last_game['AST'])
            
            # טבלה
            st.dataframe(pd.DataFrame({
                'Steals': [last_game['STL']],
                'Blocks': [last_game['BLK']],
                'Minutes': [last_game['MIN']]
            }), hide_index=True)
            
            # --- כאן הקסם: גרף גם למשחק עבר ---
            st.subheader("📈 Scoring Timeline (Last Game)")
            with st.spinner('Loading play-by-play data...'):
                df_chart = generate_chart_data(game_id, deni_id, is_live=False)
                if not df_chart.empty:
                    st.line_chart(df_chart, x="Minute", y="Points")
                else:
                    st.write("Not enough data for graph.")
            
        else:
            st.write("No games found for this season yet.")
            
    except Exception as e:
        st.error(f"Could not load history: {e}")

if st.button('Refresh'):
    st.rerun()

