import streamlit as st
import pandas as pd
from nba_api.live.nba.endpoints import scoreboard, boxscore
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

# --- הגדרות עיצוב ---
st.set_page_config(page_title="Deni Stats", page_icon="🏀")

st.title("🏀 Deni Avdija Tracker")

# פונקציה למציאת ה-ID
@st.cache_data
def get_player_id():
    p = players.find_players_by_full_name("Deni Avdija")
    return p[0]['id'] if p else None

deni_id = get_player_id()

if not deni_id:
    st.error("Player not found!")
    st.stop()

# --- בדיקת משחק חי ---
board = scoreboard.ScoreBoard()
games = board.games.get_dict()
live_game_found = False

st.write("Checking for live games...")

for game in games:
    if game['gameStatus'] == 2: # משחק פעיל
        try:
            box = boxscore.BoxScore(game_id=game['gameId']).game.get_dict()
            all_players = box['homeTeam']['players'] + box['awayTeam']['players']
            
            for p in all_players:
                if p['personId'] == deni_id:
                    live_game_found = True
                    st.success(f"🔴 LIVE: {box['awayTeam']['teamName']} vs {box['homeTeam']['teamName']}")
                    
                    # הצגת סטטיסטיקה בזמן אמת
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Points", p['statistics']['points'])
                    col2.metric("Rebounds", p['statistics']['reboundsTotal'])
                    col3.metric("Assists", p['statistics']['assists'])
                    
                    st.write(f"⏱️ Minutes: {p['statistics']['minutes']}")
                    st.write(f"📊 FG: {p['statistics']['fieldGoalsMade']}/{p['statistics']['fieldGoalsAttempted']}")
                    break
        except:
            continue

# --- אם אין משחק חי: משחק אחרון ---
if not live_game_found:
    st.info("⚪ No live game right now. Showing last game stats:")
    
    try:
        # משיכת נתונים
        gamelog = playergamelog.PlayerGameLog(player_id=deni_id)
        df = gamelog.get_data_frames()[0]
        
        if not df.empty:
            last_game = df.iloc[0]
            
            st.subheader(f"📅 {last_game['GAME_DATE']}")
            st.caption(f"Matchup: {last_game['MATCHUP']} | Result: {last_game['WL']}")
            
            # מדדים גדולים
            col1, col2, col3 = st.columns(3)
            col1.metric("Points", last_game['PTS'])
            col2.metric("Rebounds", last_game['REB'])
            col3.metric("Assists", last_game['AST'])
            
            # טבלה קטנה לנתונים נוספים
            st.dataframe(pd.DataFrame({
                'Steals': [last_game['STL']],
                'Blocks': [last_game['BLK']],
                'Minutes': [last_game['MIN']]
            }), hide_index=True)
            
        else:
            st.write("No games found for this season yet.")
            
    except Exception as e:
        st.error(f"Error fetching history: {e}")

# כפתור רענון
if st.button('Refresh Data'):

    st.rerun()
