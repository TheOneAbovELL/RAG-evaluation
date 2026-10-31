"""Accounts (admin only): list users, add one, change a role, reset a password, remove an account."""

import pandas as pd
import streamlit as st

from rag_workbench.ui.auth import current_role, current_user
from rag_workbench.ui.state import context_or_stop
from rag_workbench.users import MIN_PASSWORD_LENGTH, ROLES, UserError, UserStore

ctx = context_or_stop()
s = ctx.settings
st.title("Accounts")
if not s.has_users or current_role(s) != "admin":
    st.warning("Managing accounts needs an admin account.")
    st.stop()

users = UserStore(s.users_path)
me = current_user()
st.caption("Roles: **viewer** can browse and export; **editor** can also start runs and edit tags and notes; "
           "**admin** can also delete runs and manage accounts. Role changes and removals apply on the user's next "
           "page load.")
entries = users.entries()
st.dataframe(pd.DataFrame(entries), hide_index=True, column_config={"created": st.column_config.TextColumn("Created")})


def flash(action, *args, **kwargs):
    """Run a UserStore action and show its outcome; never lets a validation error crash the page."""
    try:
        outcome = action(*args, **kwargs)
    except UserError as exc:
        st.error(str(exc))
        return False
    if outcome is False:
        st.error("No such user.")
        return False
    return True


st.header("Add an account")
with st.form("add_user", clear_on_submit=True):
    new_name = st.text_input("Username", key="add_name")
    new_password = st.text_input(f"Password ({MIN_PASSWORD_LENGTH}+ characters)", type="password", key="add_password")
    new_role = st.selectbox("Role", ROLES, index=ROLES.index("editor"), key="add_role")
    submitted = st.form_submit_button("Add user", key="add_user_submit")
if submitted and flash(users.add, new_name, new_password, role=new_role):
    st.success(f"Added {new_name.strip().lower()}.")
    st.rerun()

st.header("Change an account")
names = [e["user"] for e in entries]
target = st.selectbox("Account", names, key="target_user")
c1, c2 = st.columns(2)
with c1.form("set_role"):
    role = st.selectbox("New role", ROLES, index=ROLES.index(next(e["role"] for e in entries if e["user"] == target)),
                        key="set_role_value")
    if st.form_submit_button("Set role", key="set_role_submit") and flash(users.set_role, target, role):
        st.success(f"{target} is now {role}.")
        st.rerun()
with c2.form("reset_password", clear_on_submit=True):
    reset = st.text_input(f"New password ({MIN_PASSWORD_LENGTH}+ characters)", type="password", key="reset_value")
    if st.form_submit_button("Reset password", key="reset_submit") and flash(users.set_password, target, reset):
        st.success(f"Password changed for {target}.")

with st.expander("Remove this account"):
    if target == me:
        st.caption("You cannot remove the account you are signed in with.")
    else:
        confirm = st.text_input("Type the username to confirm", key="remove_confirm")
        removing = st.button("Remove account", disabled=confirm.strip() != target, key="remove_user")
        if removing and flash(users.remove, target):
            st.success(f"Removed {target}.")
            st.rerun()
