import streamlit as st
import pandas as pd
import plotly.express as px

# Set up page config
st.set_page_config(page_title="Usage Analysis Report", page_icon="📊", layout="wide")

st.title("📊 Dynamic Setup Box Usage Report")
st.markdown("Analyze usage hours per room, day, or month for Model 2 Setup Boxes.")

@st.cache_data
def load_data(file_path):
    df = pd.read_excel(file_path)
    # Filter for model 2
    df = df[df['product_id'] == 2].copy()
    
    # Load MAC to Room mapping
    import os
    mapping = {}
    map_file = "Mac to Room.txt"
    if not os.path.exists(map_file):
        map_file = r"C:\Users\Dell\Documents\Mac to Room.txt"
    if os.path.exists(map_file):
        with open(map_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("PRO|Room"): continue
                parts = line.split("|") if "|" in line else line.split("(")
                if len(parts) >= 2 and parts[1].strip():
                    mac = parts[0].strip().lower()
                    room = parts[1].strip()
                    mapping[mac] = room
    
    # Apply mapping to CUID (MAC ID -> Room Number), None if not found
    df['cuid'] = df['cuid'].astype(str).str.lower().apply(lambda x: mapping.get(x, None))
    # Drop records with no matching room number
    df = df[df['cuid'].notna()]
    
    # Parse datetime
    df['play_time'] = pd.to_datetime(df['play_time_str'])
    df = df.sort_values(by=['cuid', 'play_time'])
    
    # Calculate difference to next song
    df['next_play_time'] = df.groupby('cuid')['play_time'].shift(-1)
    df['duration_sec'] = (df['next_play_time'] - df['play_time']).dt.total_seconds()
    
    # Extract date and month elements
    df['play_date'] = df['play_time'].dt.date
    df['play_month'] = df['play_time'].dt.to_period('M').astype(str)
    
    return df

with st.spinner("Loading Excel Data..."):
    # Assuming the file is fixed at the user's Downloads folder
    file_path = "only CXPro.xlsx"
    try:
        raw_df = load_data(file_path)
    except Exception as e:
        st.error(f"Error loading file: {e}")
        st.stop()

st.sidebar.header("Settings")
max_song_mins = st.sidebar.slider(
    "Max assumed song length (mins)",
    min_value=1, max_value=30, value=10,
    help="If the gap between two songs is larger than this, we assume the machine was idle and cap the duration."
)

default_min = st.sidebar.slider(
    "Default duration for last song (mins)",
    min_value=1, max_value=10, value=4,
    help="When there is no next song, what should be the assumed length?"
)

st.sidebar.header("Filters")
room_list = ["All Rooms"] + sorted(raw_df['cuid'].dropna().unique().tolist())
selected_room = st.sidebar.selectbox("Select specific room to analyze:", room_list)

# Apply limits and filters
df = raw_df.copy()
if selected_room != "All Rooms":
    df = df[df['cuid'] == selected_room]

max_sec = max_song_mins * 60
def_sec = default_min * 60

# Cap the duration per song
# If it's NaN (last song), fill with default
df['duration_sec'] = df['duration_sec'].fillna(def_sec)
# If it's too large, cap it
df['duration_sec'] = df['duration_sec'].clip(upper=max_sec)

# Convert to hours for easier analysis
df['duration_hours'] = df['duration_sec'] / 3600.0

# ---- LAYOUT ----
st.header("Overview")
col1, col2, col3 = st.columns(3)
col1.metric("Total Records Analyzed", f"{len(df):,}")
col2.metric("Total Unique Rooms (Machines)", f"{df['cuid'].nunique():,}")
col3.metric("Total Usage Hours", f"{df['duration_hours'].sum():,.2f}")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Usage per Day")
    daily_usage = df.groupby('play_date')['duration_hours'].sum().reset_index()
    fig_daily = px.bar(daily_usage, x='play_date', y='duration_hours',
                       title="Daily Usage Hours",
                       labels={'play_date': 'Date', 'duration_hours': 'Total Hours'},
                       template='plotly_dark')
    st.plotly_chart(fig_daily, use_container_width=True)

with col_right:
    st.subheader("Usage per Month")
    monthly_usage = df.groupby('play_month')['duration_hours'].sum().reset_index()
    fig_monthly = px.bar(monthly_usage, x='play_month', y='duration_hours',
                         title="Monthly Usage Hours",
                         labels={'play_month': 'Month', 'duration_hours': 'Total Hours'},
                         color_discrete_sequence=['#ff9f43'],
                         template='plotly_dark')
    st.plotly_chart(fig_monthly, use_container_width=True)

st.divider()

st.subheader("Usage per Room (Machine)")
# Top N machines slider
top_n = st.slider("Select number of top rooms to display:", 10, 100, 20)

room_usage = df.groupby('cuid')['duration_hours'].sum().reset_index().sort_values(by='duration_hours', ascending=False)

fig_room = px.bar(room_usage.head(top_n), x='cuid', y='duration_hours',
                  title=f"Top {top_n} Rooms by Usage Hours",
                  labels={'cuid': 'Room (Machine CUID)', 'duration_hours': 'Total Hours'},
                  color='duration_hours',
                  color_continuous_scale='Viridis',
                  template='plotly_dark')
# Make x-axis categorical so it doesn't get treated as purely continuous numbers if they are numeric
fig_room.update_xaxes(type='category')
st.plotly_chart(fig_room, use_container_width=True)

st.divider()

st.subheader("Detailed Data")
if st.checkbox("Show Raw Processed Data"):
    st.dataframe(df[['cuid', 'video_id', 'play_time', 'duration_sec', 'duration_hours']])

