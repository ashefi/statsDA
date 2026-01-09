import streamlit as st
import pandas as pd
import re
from nba_api.live.nba.endpoints import scoreboard, boxscore, playbyplay
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

# --- הגדרות עמוד ---
st.set_page_config(page_title="Deni Stats", page_icon="🏀")
st.title("🏀 Deni Avdija Tracker")

# --- פונקציות עזר ---

@st.cache_data
def get_player_id():
    p = players.find_players_by_full_name("Deni Avdija")
    return p[0]['id'] if p else None

# פונקציה שממירה זמן שעון (למשל PT10M30S) לדקה במשחק (0 עד 48)
def parse_nba_clock(period, clock_str):
    try:
        # הפורמט מגיע כ- PT12M00.00S
        match = re.search(r'PT(\d+)M(\d+)\.', clock_str)
        if match:
            minutes_left = int(match.group(1))
            seconds_left = int(match.group(2))
            
            # חישוב כמה דקות עברו מתחילת המשחק
            # כל רבע הוא 12 דקות
            quarter_start_time = (period - 1) * 12
            minutes_passed_in_quarter = 12 - (minutes_left + seconds_left/60)
            
            return quarter_start_time + minutes_passed_in_quarter
    except:
        return (period - 1) * 12
    return 0

# --- לוגיקה ראשית ---

deni_id = get_player_id()
if not deni_id:
    st.error("Player not found!")
    st.stop()

# בדיקת משחקים חיים
board = scoreboard.ScoreBoard()
games = board.games.get_dict()
live_game_found = False
game_id_found = None

st.write("Checking for live games...")

for game in games:
    if game['gameStatus'] == 2: # משחק פעיל
        try:
            # בדיקה אם דני משחק במשחק הזה
            box = boxscore.BoxScore(game_id=game['gameId']).game.get_dict()
            all_players = box['homeTeam']['players'] + box['awayTeam']['players']
            
            player_stats = None
            for p in all_players:
                if p['personId'] == deni_id:
                    player_stats = p
                    break
            
            if player_stats:
                live_game_found = True
                game_id_found = game['gameId']
                
                # --- תצוגת נתונים ראשית ---
                st.success(f"🔴 LIVE: {box['awayTeam']['teamName']} vs {box['homeTeam']['teamName']}")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Points", player_stats['statistics']['points'])
                col2.metric("Rebounds", player_stats['statistics']['reboundsTotal'])
                col3.metric("Assists", player_stats['statistics']['assists'])
                
                st.caption(f"Minutes: {player_stats['statistics']['minutes']} | FG: {player_stats['statistics']['fieldGoalsMade']}/{player_stats['statistics']['fieldGoalsAttempted']}")

                # --- יצירת הגרף (Play by Play) ---
                st.subheader("📈 Points Progression")
                try:
                    pbp = playbyplay.PlayByPlay(game_id_found).get_dict()
                    actions = pbp['game']['actions']
                    
                    chart_data = []
                    running_score = 0
                    
                    # נקודת התחלה (0,0)
                    chart_data.append({"Minute": 0, "Points": 0})

                    for action in actions:
                        # בדיקה אם הפעולה קשורה לדני והיא קליעה (סל או עונשין)
                        if action['personId'] == deni_id and action['isScore'] == 1:
                            # חישוב הזמן
                            game_minute = parse_nba_clock(action['period'], action['clock'])
                            
                            # עדכון הניקוד המצטבר (אנחנו סומכים שהסדר כרונולוגי)
                            # אבל ה-API לפעמים נותן רק את סוג הזריקה, אז נחלץ מהתיאור או נספור לבד
                            # גישה פשוטה: נחפש כמה נקודות זה שווה
                            points_added = 0
                            desc = action['description']
                            if "Free Throw" in desc: points_added = 1
                            elif "3pt Shot" in desc: points_added = 3
                            else: points_added = 2
                            
                            running_score += points_added
                            chart_data.append({"Minute": game_minute, "Points": running_score})
                    
                    # הוספת הנקודה העכשווית (סוף הגרף)
                    current_min_str = player_stats['statistics']['minutes']
                    # המרת דקות מחרוזת למספר (בערך)
                    try:
                        curr_min_val = float(current_min_str.replace("PT","").replace("M",""))
                    except:
                        curr_min_val = chart_data[-1]["Minute"] if chart_data else 0

                    if running_score > 0:
                        chart_data.append({"Minute": curr_min_val, "Points": running_score})
                        
                        df_chart = pd.DataFrame(chart_data)
                        st.line_chart(df_chart, x="Minute", y="Points")
                    else:
                        st.info("No points scored yet to show on graph.")

                except Exception as e:
                    st.write("Graph data not available yet.")
                    print(e)

                break # יציאה מהלולאה כי מצאנו משחק
        except:
            continue

# --- אם אין משחק חי: הצגת משחק אחרון ---
if not live_game_found:
    st.info("⚪ No live game right now. Showing last game stats:")
    
    try:
        gamelog = playergamelog.PlayerGameLog(player_id=deni_id)
        df = gamelog.get_data_frames()[0]
        
        if not df.empty:
            last_game = df.iloc[0]
            
            st.subheader(f"📅 {last_game['GAME_DATE']}")
            st.caption(f"Matchup: {last_game['MATCHUP']} | Result: {last_game['WL']}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Points", last_game['PTS'])
            col2.metric("Rebounds", last_game['REB'])
            col3.metric("Assists", last_game['AST'])
            
            # טבלה נקייה (בלי האינדקס 0)
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
