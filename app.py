import os
from datetime import datetime

import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

# --------------------------------------------------------------------------
# Lakebase connection (OAuth token rotation)
# --------------------------------------------------------------------------
# Databricks Apps connect to Lakebase using short-lived OAuth tokens instead
# of a static password. We generate a fresh token on every new connection so
# the pool never uses an expired credential.
# --------------------------------------------------------------------------

w = WorkspaceClient()


class OAuthConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", **kwargs):
        endpoint_name = os.environ["ENDPOINT_NAME"]
        credential = w.postgres.generate_database_credential(endpoint=endpoint_name)
        kwargs["password"] = credential.token
        return super().connect(conninfo, **kwargs)


@st.cache_resource
def get_pool():
    username = os.environ["PGUSER"]
    host = os.environ["PGHOST"]
    port = os.environ.get("PGPORT", "5432")
    database = os.environ["PGDATABASE"]
    sslmode = os.environ.get("PGSSLMODE", "require")

    return ConnectionPool(
        conninfo=f"dbname={database} user={username} host={host} port={port} sslmode={sslmode}",
        connection_class=OAuthConnection,
        min_size=1,
        max_size=10,
        open=True,
        kwargs={"row_factory": dict_row},
    )


def run_query(query, params=None, fetch=True):
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params or ())
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None


# --------------------------------------------------------------------------
# Data access helpers
# --------------------------------------------------------------------------

STATUSES = ["open", "in_progress", "resolved", "closed"]
PRIORITIES = ["low", "medium", "high", "urgent"]


def get_tickets(status_filter=None):
    if status_filter and status_filter != "All":
        return run_query(
            "SELECT * FROM tickets WHERE status = %s ORDER BY created_at DESC",
            (status_filter,),
        )
    return run_query("SELECT * FROM tickets ORDER BY created_at DESC")


def get_ticket(ticket_id):
    rows = run_query("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
    return rows[0] if rows else None


def get_messages(ticket_id):
    return run_query(
        "SELECT * FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,),
    )


def create_ticket(title, created_by, priority, category):
    run_query(
        """
        INSERT INTO tickets (title, status, priority, category, created_by)
        VALUES (%s, 'open', %s, %s, %s)
        """,
        (title, priority, category, created_by),
        fetch=False,
    )


def add_message(ticket_id, message_text, author):
    run_query(
        """
        INSERT INTO ticket_messages (ticket_id, message_text, author)
        VALUES (%s, %s, %s)
        """,
        (ticket_id, message_text, author),
        fetch=False,
    )


def update_status(ticket_id, new_status):
    run_query(
        "UPDATE tickets SET status = %s WHERE ticket_id = %s",
        (new_status, ticket_id),
        fetch=False,
    )


def delete_ticket(ticket_id):
    run_query("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,), fetch=False)


def get_stats():
    return run_query(
        """
        SELECT status, COUNT(*) AS count
        FROM tickets
        GROUP BY status
        ORDER BY status
        """
    )


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

st.set_page_config(page_title="Support Ticketing System", page_icon="🎫", layout="wide")

st.title("🎫 Support Ticketing System")
st.caption("Backed by Lakebase — Databricks' managed Postgres")

if "selected_ticket_id" not in st.session_state:
    st.session_state.selected_ticket_id = None

try:
    # --- Stats bar -----------------------------------------------------
    stats = get_stats()
    if stats:
        cols = st.columns(len(stats) + 1)
        total = sum(s["count"] for s in stats)
        cols[0].metric("Total tickets", total)
        for i, s in enumerate(stats, start=1):
            cols[i].metric(s["status"].replace("_", " ").title(), s["count"])

    st.divider()

    left, right = st.columns([1, 1.3], gap="large")

    # --- Left: ticket list + create form --------------------------------
    with left:
        st.subheader("Tickets")

        status_filter = st.selectbox("Filter by status", ["All"] + STATUSES)
        tickets = get_tickets(status_filter)

        if not tickets:
            st.info("No tickets found for this filter.")
        else:
            for t in tickets:
                label = f"**#{t['ticket_id']} — {t['title']}**  \n" \
                        f"`{t['status']}` · `{t['priority']}` · {t['created_by']}"
                if st.button(label, key=f"ticket_{t['ticket_id']}", use_container_width=True):
                    st.session_state.selected_ticket_id = t["ticket_id"]

        st.divider()
        st.subheader("➕ Create a new ticket")

        with st.form("new_ticket_form", clear_on_submit=True):
            new_title = st.text_input("Title")
            new_author = st.text_input("Your name / email")
            new_priority = st.selectbox("Priority", PRIORITIES, index=1)
            new_category = st.text_input("Category (optional)", value="")
            submitted = st.form_submit_button("Create ticket")

            if submitted:
                if not new_title.strip() or not new_author.strip():
                    st.error("Title and your name/email are required.")
                else:
                    create_ticket(new_title.strip(), new_author.strip(), new_priority, new_category.strip() or None)
                    st.success(f"Ticket '{new_title}' created.")
                    st.rerun()

    # --- Right: ticket detail --------------------------------------------
    with right:
        st.subheader("Ticket details")

        ticket_id = st.session_state.selected_ticket_id
        if not ticket_id:
            st.info("Select a ticket on the left to view its messages.")
        else:
            ticket = get_ticket(ticket_id)
            if not ticket:
                st.warning("This ticket no longer exists.")
                st.session_state.selected_ticket_id = None
            else:
                st.markdown(f"### #{ticket['ticket_id']} — {ticket['title']}")
                meta_cols = st.columns(3)
                meta_cols[0].write(f"**Priority:** {ticket['priority']}")
                meta_cols[1].write(f"**Category:** {ticket['category'] or '—'}")
                meta_cols[2].write(f"**Created by:** {ticket['created_by']}")
                st.caption(f"Created at {ticket['created_at']}")

                new_status = st.selectbox(
                    "Status", STATUSES, index=STATUSES.index(ticket["status"]) if ticket["status"] in STATUSES else 0,
                    key=f"status_{ticket_id}",
                )
                if new_status != ticket["status"]:
                    if st.button("Update status", key=f"update_status_{ticket_id}"):
                        update_status(ticket_id, new_status)
                        st.success("Status updated.")
                        st.rerun()

                st.divider()
                st.markdown("**Messages**")
                messages = get_messages(ticket_id)
                if not messages:
                    st.caption("No messages yet.")
                for m in messages:
                    with st.chat_message("user" if m["author"] != "support@example.com" else "assistant"):
                        st.write(m["message_text"])
                        st.caption(f"{m['author']} · {m['created_at']}")

                with st.form(f"add_message_form_{ticket_id}", clear_on_submit=True):
                    msg_text = st.text_area("Add a message")
                    msg_author = st.text_input("Author (name/email)")
                    msg_submitted = st.form_submit_button("Add message")
                    if msg_submitted:
                        if not msg_text.strip() or not msg_author.strip():
                            st.error("Message and author are required.")
                        else:
                            add_message(ticket_id, msg_text.strip(), msg_author.strip())
                            st.success("Message added.")
                            st.rerun()

                st.divider()
                with st.expander("⚠️ Delete this ticket"):
                    st.write("This will permanently delete the ticket and all its messages.")
                    confirm = st.checkbox("I understand this cannot be undone", key=f"confirm_delete_{ticket_id}")
                    if st.button("Delete ticket", disabled=not confirm, key=f"delete_{ticket_id}"):
                        delete_ticket(ticket_id)
                        st.session_state.selected_ticket_id = None
                        st.success("Ticket deleted.")
                        st.rerun()

except KeyError as e:
    st.error(
        f"Missing required environment variable: {e}. "
        "Make sure PGHOST, PGDATABASE, PGUSER, ENDPOINT_NAME are set in app.yaml."
    )
except Exception as e:
    st.error(f"Something went wrong talking to Lakebase: {e}")
