import streamlit as st
import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players
from nba_api.live.nba.endpoints import scoreboard, boxscore

# --- הגדרות עיצוב ---
st.set_page_config(page_title="Deni Stats", page_icon="🏀")
st.title("🏀 Deni Avdija Tracker")

# --- פונקציות עזר ---

@st.cache_data
def get_player_info():
    try:
        p = players.find_players_by_full_name("Deni Avdija")
        return p[0] if p else None
    except:
        return None

# --- לוגיקה ראשית ---

player = get_player_info()
if not player:
    st.error("Player not found")
    st.stop()
    
deni_id = player['id']

# בדיקת משחק חי
board = scoreboard.ScoreBoard()
games_dict = board.games.get_dict()
live_found = False

st.write("Checking status...")

for game in games_dict:
    if game['gameStatus'] == 2: # משחק פעיל
        try:
            bx = boxscore.BoxScore(game['gameId']).game.get_dict()
            players_list = bx['homeTeam']['players'] + bx['awayTeam']['players']
            for p in players_list:
                if p['personId'] == deni_id:
                    live_found = True
                    st.success(f"🔴 LIVE: {bx['awayTeam']['teamName']} vs {bx['homeTeam']['teamName']}")
                    
                    # נתונים בולטים
                    stats = p['statistics']
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Points", stats['points'])
                    c2.metric("Rebounds", stats['reboundsTotal'])
                    c3.metric("Assists", stats['assists'])
                    
                    st.divider()
                    
                    # טבלה מורחבת
                    st.caption("Live Stats:")
                    st.dataframe(pd.DataFrame({
                        'Minutes': [stats['minutes']],
                        'FG': [f"{stats['fieldGoalsMade']}/{stats['fieldGoalsAttempted']}"],
                        '3PT': [f"{stats['threePointersMade']}/{stats['threePointersAttempted']}"],
                        'FT': [f"{stats['freeThrowsMade']}/{stats['freeThrowsAttempted']}"],
                        'Blocks': [stats['blocks']],
                        'Steals': [stats['steals']],
                        'Turnovers': [stats['turnovers']]
                    }), hide_index=True)
                    
                    break
        except: pass

# אם אין משחק חי - נתוני היסטוריה (משחק אחרון)
if not live_found:
    try:
        log = playergamelog.PlayerGameLog(player_id=deni_id)
        df_log = log.get_data_frames()[0]
        
        if not df_log.empty:
            last = df_log.iloc[0]
            
            # כותרת עם התאריך והיריבה
            st.info(f"Last Game: {last['GAME_DATE']}")
            st.caption(f"Matchup: {last['MATCHUP']} | Result: {last['WL']}")
            
            # כרטיסי מידע גדולים
            c1, c2, c3 = st.columns(3)
            c1.metric("Points", last['PTS'])
            c2.metric("Rebounds", last['REB'])
            c3.metric("Assists", last['AST'])

            st.divider()

            # טבלה מסודרת עם שאר הנתונים
            st.caption("Box Score:")
            st.dataframe(pd.DataFrame({
                'MIN': [last['MIN']],
                'FG': [f"{last['FGM']}/{last['FGA']}"],
                '3PT': [f"{last['FG3M']}/{last['FG3A']}"],
                'FT': [f"{last['FTM']}/{last['FTA']}"],
                'STL': [last['STL']],
                'BLK': [last['BLK']],
                'TOV': [last['TOV']],
                '+/-': [last['PLUS_MINUS']]
            }), hide_index=True)
            
        else:
            st.warning("No games found for this season yet.")
            
    except Exception as e:
        st.error(f"Error loading data: {e}")

# כפתור רענון
if st.button("Refresh Data"):
    st.rerun()
