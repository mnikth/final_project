import streamlit as st
import datetime as dt
import json
import pandas as pd
from ai import client, system_prompt, get_json_response
import base64

st.set_page_config(page_title="Daily Schedule Buddy", layout="centered")

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_png_as_page_bg(png_file):
    bin_str = get_base64_of_bin_file(png_file)
    page_bg_img = '''
    <style>
    body {
    background-image: url("data:image/png;base64,%s");
    background-size: cover;
    }
    </style>
    ''' % bin_str
    
    st.markdown(page_bg_img, unsafe_allow_html=True)
    return

set_png_as_page_bg('bg.jpg')
if "tasks" not in st.session_state:
    st.session_state.tasks = []

if "chat" not in st.session_state:
    st.session_state.chat = [
        {"role": "assistant", "content": "Hi! Add your tasks, then I’ll build a timed schedule"}
    ]

if "last_schedule" not in st.session_state:
    st.session_state.last_schedule = None  # dict {time_str: description}

if "schedule_history" not in st.session_state:
    st.session_state.schedule_history = []

TIME_FMT = "%Y-%m-%d %I:%M %p"

def parse_time_key(time_str: str):
    try:
        return dt.datetime.strptime(time_str.strip(), TIME_FMT)
    except Exception:
        return None

def build_user_prompt(entertainment: str, available_hours: float, extra_notes: str) -> str:
    if not st.session_state.tasks:
        return (
            "I have no tasks yet. Please tell me to add tasks with deadlines and priorities, "
            "and then create a schedule."
        )

    today = dt.date.today()
    day_start = dt.datetime.combine(today, dt.time(8, 0))
    day_end = day_start + dt.timedelta(hours=available_hours)

    task_lines = []
    for i, t in enumerate(st.session_state.tasks, start=1):
        task_lines.append(
            f"{i}. Task: {t['name']}\n"
            f"   Deadline: {t['deadline_str']}\n"
            f"   Priority: {t['priority']}\n"
            f"   Notes: {t['notes'] or 'None'}"
        )

    prompt = f"""
Create a schedule for today.

Time window:
- Start: {day_start.strftime(TIME_FMT)}
- End: {day_end.strftime(TIME_FMT)}

Entertainment / break activity: {entertainment}

Tasks (with deadlines + priorities):
{chr(10).join(task_lines)}

Extra notes / constraints:
{extra_notes if extra_notes.strip() else "None"}

IMPORTANT OUTPUT RULES:
- Output ONLY valid JSON (no extra text).
- The JSON MUST look like this:
{{
  "YYYY-MM-DD HH:MM AM/PM": "what to do at that time"
}}
- Use 30 or 60 minute increments
"""
    return prompt.strip()

def generate_schedule(entertainment: str, available_hours: float, extra_notes: str):
    user_prompt = build_user_prompt(entertainment, available_hours, extra_notes)
    schedule = get_json_response(client, system_prompt, user_prompt)

    cleaned = {}
    parsed_items = []
    for k, v in schedule.items():
        t = parse_time_key(k)
        if t is not None:
            parsed_items.append((t, str(v)))

    parsed_items.sort(key=lambda x: x[0])
    for t, v in parsed_items:
        cleaned[t.strftime(TIME_FMT)] = v

    st.session_state.last_schedule = cleaned
    return cleaned

def schedule_to_dataframe(schedule_dict: dict) -> pd.DataFrame:
    rows = []
    for time_str, activity in schedule_dict.items():
        t = parse_time_key(time_str)
        rows.append({
            "Time": time_str,
            "Activity": activity,
            "SortKey": t if t else dt.datetime.max
        })
    df = pd.DataFrame(rows).sort_values("SortKey").drop(columns=["SortKey"])
    return df

st.title("AI Schedule Maker")

# ---------------- SIDEBAR (UNCHANGED) ----------------
with st.sidebar:
    st.header("Add a Task")

    task_name = st.text_input("Task name", placeholder="Math homework")
    c1, c2 = st.columns(2)
    with c1:
        deadline_date = st.date_input("Deadline date", value=dt.date.today())
    with c2:
        deadline_time = st.time_input("Deadline time", value=dt.time(17, 0))

    priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
    notes = st.text_input("Notes (optional)", placeholder="e.g., takes 30 min")

    if st.button("Add task", use_container_width=True):
        if task_name.strip() == "":
            st.warning("Please type a task name.")
        else:
            deadline_dt = dt.datetime.combine(deadline_date, deadline_time)
            st.session_state.tasks.append({
                "name": task_name.strip(),
                "deadline_str": deadline_dt.strftime(TIME_FMT),
                "priority": priority,
                "notes": notes.strip()
            })
            st.success("Task added!")

    st.divider()
    st.header("Day Settings")
    available_hours = st.slider("How many hours do you have today?", 1.0, 16.0, 6.0, 0.5)
    entertainment = st.text_input("Entertainment / break activity", value="YouTube / games / music")
    extra_notes = st.text_area("Extra notes (optional)", placeholder="Example: No work after 8pm.")

    st.divider()
    st.header("Clear / Reset")

    colA, colB = st.columns(2)
    if colA.button("Clear tasks", use_container_width=True):
        st.session_state.tasks = []
        st.session_state.last_schedule = None
        st.toast("Tasks cleared")

    if colB.button("Clear schedule", use_container_width=True):
        st.session_state.last_schedule = None
        st.toast("Schedule cleared")

    st.divider()
    st.header("Chat Controls")

    if st.button("Clear chat", use_container_width=True):
        st.session_state.chat = [
            {"role": "assistant", "content": "Chat cleared! Add tasks and generate a new schedule :)"}
        ]
        st.toast("Chat cleared")

st.subheader("Your Tasks")

if not st.session_state.tasks:
    st.info("No tasks yet. Add some from the sidebar!")
else:
    with st.expander("View / delete tasks", expanded=True):
        for idx, t in enumerate(st.session_state.tasks):
            a, b, c = st.columns([5, 3, 2])
            with a:
                st.write(f"**{t['name']}**")
                if t["notes"]:
                    st.caption(t["notes"])
            with b:
                st.write(f"{t['deadline_str']}")
                st.caption(f"Priority: {t['priority']}")
            with c:
                if st.button("Delete", key=f"del_{idx}"):
                    st.session_state.tasks.pop(idx)
                    st.rerun()


st.subheader("Your Timed Schedule")

gen1, gen2 = st.columns([2, 1])

with gen1:
    if st.button("Generate schedule", use_container_width=True):
        generate_schedule(entertainment, available_hours, extra_notes)
        st.session_state.chat.append({"role": "user", "content": "Generate a timed schedule for today."})
        st.session_state.chat.append({"role": "assistant", "content": "Done! I put each activity at a specific time."})

with gen2:
    if st.session_state.last_schedule:
        st.download_button(
            "Download schedule.json",
            data=json.dumps(st.session_state.last_schedule, indent=2),
            file_name="schedule.json",
            mime="application/json",
            use_container_width=True
        )

if st.session_state.last_schedule:
    schedule = st.session_state.last_schedule
    df = schedule_to_dataframe(schedule)

    st.markdown("### Schedule")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("Mark schedule as complete", use_container_width=True):
        st.session_state.schedule_history.append({
            "date": dt.date.today().isoformat(),
            "schedule": st.session_state.last_schedule
        })
        st.session_state.last_schedule = None
        st.toast("Schedule marked as complete!")
        st.rerun()
else:
    st.info("Click **Generate schedule** to see your plan here.")


st.subheader("Completed Schedule History")

if not st.session_state.schedule_history:
    st.info("No completed schedules yet.")
else:
    for i, item in enumerate(reversed(st.session_state.schedule_history), start=1):
        with st.expander(f"Schedule {i} — {item['date']}"):
            hist_df = schedule_to_dataframe(item["schedule"])
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

st.subheader("Chat")

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_chat = st.chat_input("Ask: 'Add more breaks' or 'Start later'")

if user_chat:
    st.session_state.chat.append({"role": "user", "content": user_chat})
    combined_notes = (extra_notes + "\nUser request: " + user_chat).strip()
    generate_schedule(entertainment, available_hours, combined_notes)
    st.session_state.chat.append({"role": "assistant", "content": "Updated your schedule based on that!"})
    st.rerun()
