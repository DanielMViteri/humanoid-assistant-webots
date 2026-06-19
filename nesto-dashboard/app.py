"""
Streamlit launcher for NESTO Care login, role routing, and page rendering.
"""

import base64
import hashlib
import hmac
import json
import time
import textwrap
from html import escape
from pathlib import Path

import streamlit as st

import page_enterprise
import page_family
import page_overview
import auth_store
from data_layer import caregiver, patient
from profile_preferences import ensure_active_care_session, load_guardian_session
from ui_theme import apply_theme


st.set_page_config(page_title="Nesto Care", page_icon=":house_with_garden:", layout="wide")


BUILD_MARKER = "routing-browser-fix-001"
SESSION_COOKIE_NAME = "nesto_active_session"
SESSION_COOKIE_SECRET = "nesto-care-routing-browser-fix-001"
SESSION_COOKIE_TTL_SECONDS = 60 * 60 * 12


LEGAL_DOCUMENTS = [
    {
        "key": "terms",
        "title": "Terms and Conditions",
        "filename": "Terms and Conditions.pdf",
        "summary": "Rules for using the Nesto Care assistant, dashboard, and support features.",
    },
    {
        "key": "privacy",
        "title": "Privacy Notice",
        "filename": "Privacy Notice.pdf",
        "summary": "How care profile data, robot updates, reminders, and memory notes are handled.",
    },
    {
        "key": "consent",
        "title": "Consent Checklist",
        "filename": "Consent Checklist.pdf",
        "summary": "The required consent obligations before care monitoring and personalization are enabled.",
    },
]


LEGAL_READER_TEXT = {
    "terms": """
Nesto Care Terms and Conditions

Nesto Care is a project support tool for a humanoid care companion. It may show reminders, family updates, approved scenario responses, care activity, and robot readiness.

Nesto Care does not provide medical diagnosis, medication dosage advice, emergency service replacement, or unsupervised clinical decision-making.

The assistant can route requests only to approved scenarios: daily support, medication reminder, object finding, wellbeing support, safety check, and general assistant response.

Users should provide accurate profile information and review important alerts with a caregiver or responsible person.

Care teams remain responsible for checking urgent concerns and confirming any real-world care action.
""",
    "privacy": """
Nesto Care Privacy Notice

Nesto Care may use care profile information, routine preferences, chat requests, robot updates, room/object events, reminders, and caregiver notes to personalize support.

MongoDB stores structured care records such as robot status, conversation events, environment events, medication events, mood events, and alerts when those records are available.

ChromaDB stores personalization memory such as profile preferences, care notes, and remembered context so Nesto can respond in a more tailored way.

The dashboard reads available project records and uses safe fallback labels only when a collection is empty or not yet implemented.

The project does not sell personal data. Data is used for the project demo, monitoring, personalization, and care-support explanation.
""",
    "consent": """
Nesto Care Consent Checklist

By continuing, the user or caregiver acknowledges consent for profile setup, daily care reminders, conversation memory, mood and wellbeing check-ins, room/object event display, family notifications, care notes used for personalization, and approved safety alerts.

Consent does not allow Nesto to diagnose conditions, change medication dosage, replace emergency services, or freely control the robot outside approved scenarios.

Consent can be reviewed later from the setup page. If consent is withdrawn, monitoring and personalization should be disabled for real deployment.
""",
}


def _resolve_document(filename):
    candidates = [
        Path(r"C:\Users\User\Downloads") / filename,
        Path("/mnt/c/Users/User/Downloads") / filename,
        Path.home() / "Downloads" / filename,
        Path(__file__).parent / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _mark_document_opened(key):
    st.session_state[f"opened_{key}"] = True


def _active_document():
    key = st.session_state.get("active_document")
    for doc in LEGAL_DOCUMENTS:
        if doc["key"] == key:
            return doc
    return None


def _document_reader_body(doc):
    key = doc["key"]
    st.caption(
        "Read this document inside Nesto Care, then mark it finished to unlock the confirmation checkbox."
    )
    st.text_area(
        "Document text",
        value=LEGAL_READER_TEXT.get(key, doc["summary"]).strip(),
        height=360,
        disabled=True,
        label_visibility="collapsed",
        key=f"doc_text_{key}",
    )
    finish_col, close_col = st.columns(2)
    if finish_col.button(
        "I agree",
        type="primary",
        use_container_width=True,
        key=f"finish_{key}",
    ):
        _mark_document_opened(key)
        st.session_state[f"accept_{key}"] = True
        st.session_state.pop("active_document", None)
        st.rerun()
    if close_col.button("Close", use_container_width=True, key=f"close_{key}"):
        st.session_state.pop("active_document", None)
        st.rerun()


def _show_document_reader():
    doc = _active_document()
    if not doc:
        return
    if hasattr(st, "dialog"):
        try:
            dialog_decorator = st.dialog(doc["title"], width="large")
        except TypeError:
            dialog_decorator = st.dialog(doc["title"])

        @dialog_decorator
        def _reader_dialog():
            _document_reader_body(doc)

        _reader_dialog()
    else:
        with st.expander(doc["title"], expanded=True):
            _document_reader_body(doc)


def _render_html(html):
    cleaned = str(html or "").strip()
    if not cleaned:
        return
    cleaned = " ".join(line.strip() for line in cleaned.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)

def _setup_goal_content(goal):
    content = {
        "daily": {
            "title": "Daily support",
            "question": f"What should Nesto gently help {patient()} remember today?",
            "plan": f"Show {patient()}'s schedule, support check-ins, and update the family app when a care task is completed.",
        },
        "medicine": {
            "title": "Medication reminders",
            "question": "Which reminder matters most for today's routine?",
            "plan": f"Give preset reminders only, record whether they were acknowledged, and show the status to {caregiver()}.",
        },
        "family": {
            "title": "Family peace of mind",
            "question": f"What should {caregiver()} be able to see quickly?",
            "plan": "Show a simple daily summary, recent Nesto messages, wellbeing indicators, and urgent alerts.",
        },
        "object": {
            "title": "Find important objects",
            "question": "Which item should Nesto be ready to help locate?",
            "plan": "Route natural requests such as finding a cane to the approved object-finder scenario and record the result.",
        },
    }
    return content.get(goal, content["daily"])


PAGES = {
    "Landing Page": {
        "group": "Product",
        "theme": "light",
        "render": page_overview.render,
    },
    "User Creation + Preferences Page": {
        "group": "Caregiver",
        "theme": "light",
        "render": page_family.profile,
    },
    "Elderly User Interface": {
        "group": "Elderly user",
        "theme": "light",
        "render": page_family.elderly_home,
    },
    "Guardian / Caregiver Dashboard": {
        "group": "Caregiver",
        "theme": "light",
        "render": page_family.family_dashboard,
    },
    "Admin / Provider / NESTO Team Dashboard": {
        "group": "Admin / team",
        "theme": "light",
        "render": page_enterprise.admin_overview,
    },
}

PAGE_ALIASES = {
    "landing": "Landing Page",
    "profile_preferences": "User Creation + Preferences Page",
    "elderly_interface": "Elderly User Interface",
    "guardian_dashboard": "Guardian / Caregiver Dashboard",
    "admin_overview": "Admin / Provider / NESTO Team Dashboard",
    "Landing": "Landing Page",
    "Product Overview": "Landing Page",
    "Home": "Elderly User Interface",
    "User Interface": "Elderly User Interface",
    "Profile & Preferences": "User Creation + Preferences Page",
    "Care Profile": "User Creation + Preferences Page",
    "Setup & Consent": "User Creation + Preferences Page",
    "Consent Details": "User Creation + Preferences Page",
    "Family App Landing": "Guardian / Caregiver Dashboard",
    "Health & Care": "Guardian / Caregiver Dashboard",
    "Guardian View": "Guardian / Caregiver Dashboard",
    "Next of Kin / Caregiver Dashboard": "Guardian / Caregiver Dashboard",
    "Next of Kin View": "Guardian / Caregiver Dashboard",
    "Admin Overview": "Admin / Provider / NESTO Team Dashboard",
    "Admin / Team View": "Admin / Provider / NESTO Team Dashboard",
    "Chat Monitor": "Admin / Provider / NESTO Team Dashboard",
    "Robot Operations": "Admin / Provider / NESTO Team Dashboard",
    "Wellbeing Monitor": "Admin / Provider / NESTO Team Dashboard",
}

ROLE_ALIASES = {
    "admin_provider": "Admin / team",
    "guardian_caregiver": "Caregiver",
    "elderly_user": "Elderly user",
    "Admin": "Admin / team",
    "Admin / Provider": "Admin / team",
    "Admin / Provider / NESTO Team": "Admin / team",
    "Provider": "Admin / team",
    "Robot": "Admin / team",
    "Patient": "Elderly user",
    "Elderly": "Elderly user",
    "Elderly User": "Elderly user",
    "Guardian": "Caregiver",
    "Guardian / Caregiver": "Caregiver",
}

PAGE_CANONICAL_BY_DISPLAY = {
    "Landing Page": "landing",
    "User Creation + Preferences Page": "profile_preferences",
    "Elderly User Interface": "elderly_interface",
    "Guardian / Caregiver Dashboard": "guardian_dashboard",
    "Admin / Provider / NESTO Team Dashboard": "admin_overview",
}

ROLE_CANONICAL_BY_DISPLAY = {
    "Product": "product",
    "Elderly user": "elderly_user",
    "Caregiver": "guardian_caregiver",
    "Admin / team": "admin_provider",
}

ROLE_DISPLAY_BY_CANONICAL = {
    "product": "Product",
    "elderly_user": "Elderly user",
    "guardian_caregiver": "Caregiver",
    "admin_provider": "Admin / team",
}

PROTECTED_DASHBOARD_PAGES = {
    "Elderly User Interface",
    "Guardian / Caregiver Dashboard",
    "Admin / Provider / NESTO Team Dashboard",
}

ROLE_DEFAULT_ROUTE = {
    "elderly_user": {
        "nav_role": "elderly_user",
        "nav_page": "elderly_interface",
    },
    "guardian_caregiver": {
        "nav_role": "guardian_caregiver",
        "nav_page": "guardian_dashboard",
    },
    "admin_provider": {
        "nav_role": "admin_provider",
        "nav_page": "admin_overview",
        "provider_tab": "overview",
    },
}

ROLE_ACCESS_BY_SESSION_ROLE = {
    "elderly_user": "Elderly user",
    "guardian_caregiver": "Caregiver",
    "admin_provider": "Admin / team",
}

SESSION_CLEAR_KEYS = (
    "active_session",
    "active_user_session",
    "active_care_session",
    "pending_login_user",
    "pending_role",
    "pending_page",
    "pending_admin_page",
    "login_error",
    "nav_role",
    "nav_page",
    "provider_tab",
    "caregiver_action_feedback",
    "last_caregiver_action",
    "last_elderly_action",
    "elderly_action",
    "nesto_action",
    "talk_to_nesto_command",
    "talk_to_nesto_response",
    "talk_to_nesto_listening",
    "talk_to_nesto_scenario",
    "selected_elderly_action",
    "last_url_action",
)


def _normalize_role(role):
    value = str(role or "").strip()
    if not value:
        return value
    if value in ROLE_DISPLAY_BY_CANONICAL:
        return ROLE_DISPLAY_BY_CANONICAL[value]
    return ROLE_ALIASES.get(value, value)


def _normalize_page(page):
    value = str(page or "").strip()
    if not value:
        return value
    return PAGE_ALIASES.get(value, value)


def _route_role_param(display_role):
    role = _normalize_role(display_role)
    return ROLE_CANONICAL_BY_DISPLAY.get(role, role)


def _route_page_param(display_page):
    page = _normalize_page(display_page)
    return PAGE_CANONICAL_BY_DISPLAY.get(page, page)


def _query_param(name):
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _cookie_signature(payload):
    return hmac.new(SESSION_COOKIE_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_session_cookie(session):
    safe_session = {
        "is_authenticated": True,
        "user_id": str(session.get("user_id") or ""),
        "email": str(session.get("email") or ""),
        "role": str(session.get("role") or ""),
        "display_name": str(session.get("display_name") or ""),
        "profile_id": str(session.get("profile_id") or ""),
        "linked_patient_ids": list(session.get("linked_patient_ids") or []),
        "expires_at": int(time.time()) + SESSION_COOKIE_TTL_SECONDS,
    }
    payload = base64.urlsafe_b64encode(json.dumps(safe_session, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return f"{payload}.{_cookie_signature(payload)}"


def _decode_session_cookie(token):
    if not token or "." not in str(token):
        return {}
    payload, signature = str(token).split(".", 1)
    if not hmac.compare_digest(signature, _cookie_signature(payload)):
        return {}
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8"))
    except Exception:
        return {}
    if int(data.get("expires_at") or 0) < int(time.time()):
        return {}
    role = str(data.get("role") or "")
    if role not in ROLE_ACCESS_BY_SESSION_ROLE:
        return {}
    user_id = str(data.get("user_id") or "")
    if not user_id:
        return {}
    return {
        "is_authenticated": True,
        "user_id": user_id,
        "email": str(data.get("email") or ""),
        "role": role,
        "display_name": str(data.get("display_name") or "Nesto user"),
        "profile_id": str(data.get("profile_id") or ""),
        "linked_patient_ids": list(data.get("linked_patient_ids") or []),
    }


def _browser_cookie_value(name):
    try:
        cookies = st.context.cookies
        return cookies.get(name)
    except Exception:
        return None


def _restore_session_from_cookie():
    if st.session_state.get("_clear_session_cookie") or st.session_state.get("_skip_cookie_restore"):
        return False
    if isinstance(st.session_state.get("active_session"), dict) and st.session_state["active_session"].get("is_authenticated"):
        return False
    session = _decode_session_cookie(_browser_cookie_value(SESSION_COOKIE_NAME))
    if not session:
        return False
    st.session_state["active_session"] = session
    st.session_state["active_user_session"] = {
        "user_id": session.get("user_id", ""),
        "email": session.get("email", ""),
        "role": session.get("role", ""),
        "display_name": session.get("display_name", ""),
        "profile_id": session.get("profile_id", ""),
        "linked_patient_ids": list(session.get("linked_patient_ids") or []),
    }
    recovered_role = ROLE_ACCESS_BY_SESSION_ROLE.get(session.get("role", ""))
    if recovered_role:
        st.session_state["access_role"] = recovered_role
    return True


def _write_session_cookie_script():
    session = st.session_state.get("active_session")
    if not isinstance(session, dict) or not session.get("is_authenticated"):
        return
    token = _encode_session_cookie(session)
    try:
        st.components.v1.html(
            f"""
            <script>
            document.cookie = "{SESSION_COOKIE_NAME}={token}; path=/; max-age={SESSION_COOKIE_TTL_SECONDS}; SameSite=Lax";
            </script>
            """,
            height=0,
        )
    except Exception:
        pass


def _clear_session_cookie_script():
    try:
        st.components.v1.html(
            f"""
            <script>
            document.cookie = "{SESSION_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax";
            </script>
            """,
            height=0,
        )
    except Exception:
        pass


def _clear_query_params(*names):
    for name in names:
        try:
            if name in st.query_params:
                del st.query_params[name]
        except Exception:
            pass


def _current_active_session():
    session = st.session_state.get("active_session")
    if isinstance(session, dict) and session.get("is_authenticated") and session.get("user_id"):
        return session

    if _restore_session_from_cookie():
        session = st.session_state.get("active_session")
        if isinstance(session, dict) and session.get("is_authenticated") and session.get("user_id"):
            return session

    legacy = st.session_state.get("active_user_session")
    if isinstance(legacy, dict) and legacy.get("user_id"):
        session = {
            "is_authenticated": True,
            "user_id": legacy.get("user_id", ""),
            "email": legacy.get("email", ""),
            "role": legacy.get("role", ""),
            "display_name": legacy.get("display_name") or legacy.get("username") or "Nesto user",
            "profile_id": legacy.get("profile_id", ""),
            "linked_patient_ids": list(legacy.get("linked_patient_ids") or []),
        }
        st.session_state["active_session"] = session
        return session
    return {}


def _has_active_session():
    return bool(_current_active_session().get("user_id"))


def _page_requires_session(role, page):
    if page == "User Creation + Preferences Page":
        profile_mode = str(_query_param("profile_mode") or st.session_state.get("profile_mode") or "").strip().lower()
        return profile_mode != "create"
    return page in PROTECTED_DASHBOARD_PAGES or role in {"Elderly user", "Caregiver", "Admin / team"}


def _session_access_role():
    role = str(_current_active_session().get("role") or "")
    return ROLE_ACCESS_BY_SESSION_ROLE.get(role, "")


def set_route(nav_role=None, nav_page=None, rerun=False, **extra):
    role = _normalize_role(nav_role) if nav_role else None
    page = _normalize_page(nav_page) if nav_page else None
    if role:
        st.session_state["access_role"] = role
        st.session_state["nav_role"] = role
        try:
            st.query_params["nav_role"] = _route_role_param(role)
        except Exception:
            pass
    if page:
        st.session_state["nav_page"] = page
        try:
            st.query_params["nav_page"] = _route_page_param(page)
        except Exception:
            pass
        group = PAGES.get(page, {}).get("group")
        if group:
            st.session_state[f"{group}_page"] = page
    for key, value in extra.items():
        if value is None:
            continue
        st.session_state[key] = value
        try:
            st.query_params[key] = value
        except Exception:
            pass
    if rerun:
        st.rerun()


def logout_user():
    for key in SESSION_CLEAR_KEYS:
        st.session_state.pop(key, None)
    for key in ("Elderly user_page", "Caregiver_page", "Admin / team_page"):
        st.session_state.pop(key, None)
    st.session_state["access_role"] = "Product"
    st.session_state["_clear_session_cookie"] = True
    st.session_state["_skip_cookie_restore"] = True
    st.session_state["logout_notice"] = "You have been logged out."
    _clear_all_query_params()
    st.rerun()


def _render_pending_notice():
    notice = st.session_state.pop("logout_notice", None)
    if notice:
        try:
            st.toast(notice)
        except Exception:
            pass
        st.markdown(
            f"""
            <div class="notice-pop" style="border:1px solid #cbdccb;background:#f4fbf6;color:#183f3a;border-radius:16px;padding:14px 18px;margin:0 auto 16px;max-width:1030px;box-shadow:0 10px 26px rgba(37,65,63,.08);font-weight:950;">
                Logged out successfully
                <span class="notice-sub" style="display:block;color:#4f7364;font-size:.9rem;font-weight:750;margin-top:4px;">{escape(notice)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    notice = st.session_state.pop("app_notice", None)
    if not notice:
        return
    title = escape(str(notice.get("title", "Nesto Care")))
    message = escape(str(notice.get("message", "")))
    st.markdown(
        f"""
        <div class="notice-pop" style="border:1px solid #cbdccb;background:#ffffff;color:#25413f;border-radius:16px;padding:14px 18px;margin:0 auto 16px;max-width:1180px;box-shadow:0 10px 26px rgba(37,65,63,.08);font-weight:950;">
            {title}
            <span class="notice-sub" style="display:block;color:#4f7364;font-size:.9rem;font-weight:750;margin-top:4px;">{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _current_port_label():
    try:
        url = str(st.context.url or "")
    except Exception:
        url = ""
    if ":" not in url:
        return "unknown"
    tail = url.split(":", 2)[-1]
    port = tail.split("/", 1)[0].split("?", 1)[0]
    return port or "unknown"


def _render_build_marker():
    session = _current_active_session()
    authenticated = bool(session.get("is_authenticated"))
    role = escape(str(session.get("role") or "none"))
    st.markdown(
        f"""
        <div style="position:fixed;right:14px;bottom:10px;z-index:999999;background:rgba(255,253,248,.95);border:1px solid #d8e4da;border-radius:12px;padding:8px 11px;color:#183f3a;font-size:11px;line-height:1.35;box-shadow:0 8px 24px rgba(24,63,58,.10);font-weight:850;">
            <div>Build: {BUILD_MARKER}</div>
            <div>Port: {_current_port_label()}</div>
            <div>Session: {'authenticated' if authenticated else 'unauthenticated'}</div>
            <div>Role: {role}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _consume_navigation_query():
    role = _normalize_role(_query_param("nav_role"))
    page = _query_param("nav_page")
    provider_tab = _query_param("provider_tab")
    guardian_id = _query_param("guardian_id")
    patient_id = _query_param("patient_id")
    consumed = False

    if provider_tab:
        st.session_state["provider_tab"] = provider_tab
        consumed = True

    page = _normalize_page(page)

    if role and page and page in PAGES and PAGES[page]["group"] == role:
        if _has_active_session() and role == "Product" and page == "Landing Page":
            default_route = ROLE_DEFAULT_ROUTE.get(str(_current_active_session().get("role") or ""), {})
            if default_route:
                set_route(
                    default_route.get("nav_role"),
                    default_route.get("nav_page"),
                    provider_tab=default_route.get("provider_tab"),
                    rerun=True,
                )
        protected = _page_requires_session(role, page)
        if protected and not _has_active_session():
            st.session_state["access_role"] = "Product"
            st.session_state["app_notice"] = {
                "title": "Sign in required",
                "message": "Please sign in before opening a protected Nesto dashboard.",
            }
            _clear_query_params("nav_role", "nav_page", "provider_tab", "guardian_id", "patient_id", "nesto_action", "caregiver_action")
            try:
                st.query_params["auth_mode"] = "signin"
            except Exception:
                pass
            st.rerun()
        session_role = _session_access_role()
        if protected and session_role and role != session_role:
            default_route = ROLE_DEFAULT_ROUTE.get(str(_current_active_session().get("role") or ""), {})
            if default_route:
                set_route(
                    default_route.get("nav_role"),
                    default_route.get("nav_page"),
                    provider_tab=default_route.get("provider_tab"),
                )
                st.session_state["app_notice"] = {
                    "title": "Opening your dashboard",
                    "message": "Nesto kept you in the dashboard for your signed-in role.",
                }
                st.rerun()
        set_route(role, page)
        if role == "Caregiver":
            if guardian_id or patient_id or "active_care_session" not in st.session_state:
                load_guardian_session(st.session_state, guardian_id or "guardian_01", patient_id or "")
            else:
                ensure_active_care_session(st.session_state)
        consumed = True

    if consumed:
        pass



def _render_public_sidebar(active_label="Home"):
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:10px 0 26px;">
            <div style="font-size:28px;">&#8962;</div>
            <div style="font-weight:950;color:#123536;font-size:18px;">Nesto Care</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<style>section[data-testid='stSidebar'] a, section[data-testid='stSidebar'] a * { text-decoration: none !important; text-decoration-line: none !important; }</style>",
        unsafe_allow_html=True,
    )
    landing_items = [
        ("&#8962;", "Home"),
        ("&#9881;", "Features"),
        ("&#128279;", "How it works"),
        ("&#128172;", "About Nesto"),
        ("?", "FAQ"),
        ("&#128274;", "Privacy Policy"),
        ("&#9635;", "Terms of Service"),
        ("&#128222;", "Contact Us"),
    ]
    for icon, label in landing_items:
        active = label == active_label
        st.sidebar.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin:4px 0;border-radius:10px;background:{'#e9f2ec' if active else 'transparent'};color:#123536;font-weight:{'850' if active else '650'};">
                <span style="width:18px;text-align:center;">{icon}</span><span>{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""
        <div style="border:1px solid #e3d8c7;border-radius:18px;padding:14px;background:#fffdf8;text-align:center;color:#123536;">
            <div style="height:122px;display:grid;place-items:center;overflow:hidden;">{_sidebar_nesto_robot()}</div>
            <b>Nesto is ready</b>
            <div style="color:#176b4d;font-size:.78rem;font-weight:900;margin-top:4px;">&#9679; Online</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_nesto_robot():
    return """
    <div class="nesto-bot" aria-label="Nesto robot mascot" style="transform:scale(.72);">
        <div class="nesto-shadow"></div>
        <div class="nesto-ear left"></div>
        <div class="nesto-ear right"></div>
        <div class="nesto-head"></div>
        <div class="nesto-face">
            <span class="nesto-eye left"></span>
            <span class="nesto-eye right"></span>
            <span class="nesto-smile"></span>
        </div>
        <div class="nesto-arm left"></div>
        <div class="nesto-arm right"></div>
        <div class="nesto-body"></div>
        <div class="nesto-heart">&#9829;</div>
        <div class="nesto-base"></div>
    </div>
    """



def _render_elderly_sidebar(active_label="Home"):
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:10px 0 26px;">
            <div style="font-size:28px;">&#8962;</div>
            <div style="font-weight:950;color:#123536;font-size:18px;">Nesto Care</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    items = [
        ("&#8962;", "Home"),
        ("&#128197;", "Today's Schedule"),
        ("&#128138;", "Take Medication"),
        ("&#128172;", "Talk to Nesto"),
        ("&#128269;", "Find My Cane"),
        ("&#128138;", "Find My Medicine"),
        ("&#128222;", "Call Caregiver"),
        ("&#9825;", "How are you feeling?"),
        ("&#9888;", "Emergency"),
        ("&#9881;", "Settings"),
    ]
    for icon, label in items:
        active = label == active_label
        st.sidebar.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin:4px 0;border-radius:10px;background:{'#e9f2ec' if active else 'transparent'};color:#123536;font-weight:{'850' if active else '650'};">
                <span style="width:18px;text-align:center;">{icon}</span><span>{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("<div style='height:64px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        """
        <div style="border:1px solid #e3d8c7;border-radius:18px;padding:14px;background:#fffdf8;text-align:center;color:#123536;">
            <div style="font-size:54px;line-height:1;">&#129302;</div>
            <b>Nesto is nearby</b>
            <a href="?logout=1" style="margin-top:12px;min-height:38px;border-radius:999px;border:1px solid #e3d8c7;background:#fffdf8;color:#183f3a !important;font-weight:900;text-decoration:none !important;display:flex;align-items:center;justify-content:center;">Log out</a>
        </div>
        """,
        unsafe_allow_html=True,
    )



def _render_caregiver_sidebar(active_label="Overview"):
    st.sidebar.markdown(
        """
        <style>
        section[data-testid='stSidebar'] a,
        section[data-testid='stSidebar'] a:visited,
        section[data-testid='stSidebar'] a:hover,
        section[data-testid='stSidebar'] a *,
        section[data-testid='stSidebar'] a span {
            text-decoration: none !important;
            text-decoration-line: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    current_section = (_query_param("caregiver_section") or "overview").strip().lower()
    section_labels = {
        "overview": "Overview",
        "messages": "Messages",
        "alerts": "Alerts",
        "activity": "Care Activity",
        "profile": "Elderly Profile",
        "notes": "Care Notes",
        "settings": "Settings",
    }
    active_label = section_labels.get(current_section, active_label)
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:10px 0 26px;">
            <div style="font-size:28px;">&#8962;</div>
            <div style="font-weight:950;color:#123536;font-size:18px;">Nesto Care</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    active_session = ensure_active_care_session(st.session_state)
    guardian_id = str(active_session.get("guardian_id") or "guardian_01")
    patient_id = str(active_session.get("assigned_patient_id") or "elderly_user_01")
    base = f"?nav_role=Caregiver&nav_page=Guardian%20%2F%20Caregiver%20Dashboard&guardian_id={guardian_id}&patient_id={patient_id}"
    items = [
        ("&#8962;", "Overview", "", f"{base}&caregiver_section=overview#cg-overview"),
        ("&#128172;", "Messages", "", f"{base}&caregiver_action=message&caregiver_section=messages#cg-message"),
        ("&#128276;", "Alerts", "5", f"{base}&caregiver_action=alerts&caregiver_section=alerts#cg-alerts"),
        ("&#128737;", "Care Activity", "", f"{base}&caregiver_section=activity#cg-activity"),
        ("&#128100;", "Elderly Profile", "", f"{base}&caregiver_section=profile#cg-profile"),
        ("&#128221;", "Care Notes", "", f"{base}&caregiver_action=note&caregiver_section=notes#cg-care-notes"),
        ("&#9881;", "Settings", "", f"{base}&caregiver_section=settings#cg-settings"),
    ]
    for icon, label, count, href in items:
        active = label == active_label
        badge_html = (
            f'<span style="margin-left:auto;background:#ef4444;color:#fff;border-radius:999px;min-width:20px;height:20px;display:inline-grid;place-items:center;font-size:.72rem;font-weight:950;">{count}</span>'
            if count
            else ""
        )
        st.sidebar.markdown(
            f"""
            <a href="{href}" style="text-decoration:none !important;display:flex;align-items:center;gap:10px;padding:10px 12px;margin:4px 0;border-radius:10px;background:{'#e9f2ec' if active else 'transparent'};color:#123536 !important;font-weight:{'850' if active else '650'};">
                <span style="width:18px;text-align:center;">{icon}</span><span>{label}</span>{badge_html}
            </a>
            """,
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("<div style='height:72px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""
        <div class="nesto-pattern-surface nesto-pattern-soft" style="border:1px solid #e3d8c7;border-radius:18px;padding:14px;background:#fffdf8;text-align:center;color:#123536;overflow:hidden;">
            <div style="height:126px;display:grid;place-items:center;overflow:visible;">{_sidebar_nesto_robot()}</div>
            <b>Nesto is ready</b>
            <div style="color:#176b4d;font-size:.78rem;font-weight:900;margin-top:4px;">&#9679; Online</div>
            <a href="?logout=1" style="margin-top:12px;min-height:38px;border-radius:999px;border:1px solid #e3d8c7;background:#fffdf8;color:#183f3a !important;font-weight:900;text-decoration:none !important;display:flex;align-items:center;justify-content:center;">Log out</a>
        </div>
        """,
        unsafe_allow_html=True,
    )



def _render_admin_sidebar(active_label="Overview"):
    current_tab = (_query_param("provider_tab") or st.session_state.get("provider_tab") or "overview").strip().lower()
    label_by_tab = {
        "overview": "Overview",
        "robot_fleet": "Robot Fleet",
        "robot": "Robot Fleet",
        "patients": "Patients",
        "guardians": "Guardian / Caregivers",
        "caregivers": "Guardian / Caregivers",
        "alerts": "Alerts",
        "telemetry": "Telemetry & Logs",
        "logs": "Telemetry & Logs",
        "care_plans": "Care Plans",
        "plans": "Care Plans",
        "reports": "Reports",
        "system_health": "System Health",
        "integrations": "System Health",
        "support_tickets": "Support Tickets",
        "tickets": "Support Tickets",
        "settings": "Settings",
    }
    active_label = label_by_tab.get(current_tab, active_label)
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:10px 0 26px;">
            <div style="font-size:28px;">&#8962;</div>
            <div style="font-weight:950;color:#123536;font-size:18px;">Nesto Care</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        """
        <style>
        section[data-testid='stSidebar'] a,
        section[data-testid='stSidebar'] a:visited,
        section[data-testid='stSidebar'] a:hover,
        section[data-testid='stSidebar'] a *,
        section[data-testid='stSidebar'] a span {
            text-decoration: none !important;
            text-decoration-line: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    base = "?nav_role=Admin%20%2F%20team&nav_page=Admin%20Overview"
    items = [
        ("overview", "&#8962;", "Overview", ""),
        ("robot_fleet", "&#129302;", "Robot Fleet", ""),
        ("patients", "&#128101;", "Patients", ""),
        ("guardians", "&#129489;", "Guardian / Caregivers", ""),
        ("alerts", "&#128276;", "Alerts", "12"),
        ("telemetry", "&#128200;", "Telemetry & Logs", ""),
        ("care_plans", "&#128203;", "Care Plans", ""),
        ("reports", "&#128196;", "Reports", ""),
        ("system_health", "&#9881;", "System Health", ""),
        ("support_tickets", "&#128172;", "Support Tickets", ""),
        ("settings", "&#9881;", "Settings", ""),
    ]
    for tab, icon, label, count in items:
        active = label == active_label
        badge_html = (
            f'<span style="margin-left:auto;background:#ef4444;color:#fff;border-radius:999px;min-width:26px;height:20px;display:inline-grid;place-items:center;font-size:.72rem;font-weight:950;">{count}</span>'
            if count
            else ""
        )
        href = f"{base}&provider_tab={tab}#admin-{tab.replace('_', '-')}"
        st.sidebar.markdown(
            f"""
            <a href="{href}" style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin:4px 0;border-radius:10px;background:{'#e9f2ec' if active else 'transparent'};color:#123536 !important;font-weight:{'850' if active else '650'};">
                <span style="width:18px;text-align:center;">{icon}</span><span>{label}</span>{badge_html}
            </a>
            """,
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("<div style='height:130px;'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        """
        <div style="border:1px solid #e5ded2;border-radius:14px;background:#fffdf8;padding:14px;color:#102f32;">
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:48px;height:48px;border-radius:999px;background:#176b4d;color:white;display:grid;place-items:center;font-weight:950;font-size:1.2rem;">A</div>
                <div><b>Provider Admin</b><br><span style="color:#65736f;font-size:.82rem;">Admin</span></div>
            </div>
            <a href="?logout=1" style="margin-top:12px;min-height:38px;border-radius:999px;border:1px solid #e3d8c7;background:#fffdf8;color:#183f3a !important;font-weight:900;text-decoration:none !important;display:flex;align-items:center;justify-content:center;">Log out</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar():
    roles = ("Product", "Elderly user", "Caregiver", "Admin / team")
    pending_role = _normalize_role(st.session_state.pop("pending_role", None))
    pending_page = st.session_state.pop("pending_page", None)
    if pending_role in roles:
        st.session_state["access_role"] = pending_role

    if pending_page in PAGE_ALIASES:
        pending_page = PAGE_ALIASES[pending_page]

    if pending_page == "User Creation + Preferences Page":
        st.session_state["access_role"] = "Caregiver"
        st.session_state["Caregiver_page"] = pending_page
    if pending_page == "Elderly User Interface":
        st.session_state["access_role"] = "Elderly user"
        st.session_state["Elderly user_page"] = pending_page

    role = st.session_state.get("access_role", "Product")
    if role == "Product" and _has_active_session():
        recovered_role = _session_access_role()
        if recovered_role:
            role = recovered_role
            st.session_state["access_role"] = recovered_role

    if role == "Caregiver" and st.session_state.get("Caregiver_page") == "User Creation + Preferences Page":
        _render_public_sidebar("Home")
        st.session_state["phone_preview"] = False
        return "User Creation + Preferences Page"

    if role == "Elderly user":
        _render_elderly_sidebar("Home")
        st.session_state["phone_preview"] = False
        return "Elderly User Interface"

    if role == "Caregiver":
        ensure_active_care_session(st.session_state)
        _render_caregiver_sidebar("Overview")
        st.session_state["phone_preview"] = False
        return "Guardian / Caregiver Dashboard"

    if role == "Admin / team":
        _render_admin_sidebar("Overview")
        st.session_state["phone_preview"] = False
        return "Admin / Provider / NESTO Team Dashboard"

    if role == "Product":
        st.session_state["phone_preview"] = False
        return "Landing Page"

    st.sidebar.title("Nesto Care")
    st.sidebar.caption("Calm companion workspace")
    if st.sidebar.button("Back to landing", use_container_width=True):
        st.session_state["access_role"] = "Product"
        st.rerun()
    st.sidebar.divider()
    st.sidebar.markdown(
        f"""
        <div style="background:#f4efe5;border:1px solid #e3d8c7;border-radius:14px;padding:14px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:42px;height:42px;border-radius:14px;background:#e9f2ec;display:flex;align-items:center;justify-content:center;color:#25413f;font-size:20px;font-weight:900;">&#8962;</div>
                <div>
                    <div style="font-weight:900;color:#25413f;">{patient()}</div>
                    <div style="font-size:.8rem;color:#6f7d7b;">Primary caregiver: {caregiver()}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    role = st.sidebar.selectbox(
        "Access as",
        roles[1:],
        key="access_role",
    )

    pages = [name for name, meta in PAGES.items() if meta["group"] == role]
    if not pending_page and role == "Admin / team":
        pending_page = st.session_state.pop("pending_admin_page", None)
    if pending_page in pages:
        st.session_state[f"{role}_page"] = pending_page
    page = st.sidebar.selectbox("Open", pages, key=f"{role}_page")
    st.sidebar.divider()
    st.session_state["phone_preview"] = False
    if role == "Elderly user":
        st.sidebar.caption(f"Simple patient view for {patient()}.")
    elif role == "Caregiver":
        st.sidebar.caption(f"Family access for {caregiver()}.")
    else:
        st.sidebar.caption("Team access for monitoring, data health, and robot operations.")
    return page



def _reset_ui_state():
    keep = set()
    for key in list(st.session_state.keys()):
        if key not in keep:
            del st.session_state[key]


def legal_gate():
    apply_theme("light")
    _render_html(
        f"""
        <div class="welcome-hero">
            <div class="welcome-nav">
                <div class="welcome-brand"><span class="welcome-logo">&#8962;</span><b>Nesto Care</b></div>
                <div class="welcome-links"><span>Robot</span><span>Family</span><span>Provider</span><b>Consent setup</b></div>
            </div>
            <div class="welcome-grid">
                <div>
                    <div class="kicker">Welcome to Nesto Care</div>
                    <div class="welcome-title">A calm companion for safer ageing at home</div>
                    <p class="welcome-copy">Nesto connects a friendly robot interface, a family companion app, and a healthcare provider dashboard around {patient()}'s daily care.</p>
                    <div class="welcome-actions">
                        <span>Warm</span><span>Trustworthy</span><span>Gentle</span><span>Home-friendly</span>
                    </div>
                </div>
                <div class="welcome-robot-panel">
                    <div class="speech-bubble">Hi {patient()}, I can help with reminders, family updates, and finding important things.</div>
                    <div class="nesto-bot" aria-label="Animated friendly Nesto robot">
                        <div class="nesto-shadow"></div><div class="nesto-ear left"></div><div class="nesto-ear right"></div><div class="nesto-head"></div><div class="nesto-face"><span class="nesto-eye left"></span><span class="nesto-eye right"></span><span class="nesto-smile"></span></div><div class="nesto-body"></div><div class="nesto-heart">&#9829;</div><div class="nesto-arm left"></div><div class="nesto-arm right"></div><div class="nesto-base"></div>
                    </div>
                    <div class="welcome-note">Consent is required before monitoring starts.</div>
                </div>
            </div>
        </div>
        """,
    )
    _render_html(
        f"""
        <div class="setup-strip">
            <div><b>{patient()}</b><span>Elderly robot interface</span></div>
            <div><b>{caregiver()}</b><span>Family companion app</span></div>
            <div><b>Nesto</b><span>Approved care scenarios only</span></div>
            <div><b>Care records + memory</b><span>Live updates stay connected behind the scenes</span></div>
        </div>
        <div class="card">
            <p class="section-title">What this setup is for</p>
            <div class="outcome-grid">
                <div class="outcome-card"><div class="outcome-icon">&#8962;</div><b>Elderly user</b><p class="muted">Large, simple buttons for schedule, medication, family calls, chat, wellbeing, and emergency support.</p></div>
                <div class="outcome-card"><div class="outcome-icon">&#9829;</div><b>Caregiver</b><p class="muted">A family app showing daily summaries, Nesto messages, reminders, trends, and urgent alerts.</p></div>
                <div class="outcome-card"><div class="outcome-icon">&#128200;</div><b>Provider team</b><p class="muted">A dashboard for robot readiness, approved scenario routing, care activity, and live records.</p></div>
            </div>
        </div>
        """,
    )

    if "setup_goal" not in st.session_state:
        st.session_state["setup_goal"] = "daily"
    _render_html('<div class="card"><p class="section-title">Choose a care goal to personalize the start</p><p class="muted">This explains what Nesto is trying to support before monitoring begins.</p></div>')
    goal_cols = st.columns(4)
    goal_buttons = [
        ("daily", "Daily support"),
        ("medicine", "Medication"),
        ("family", "Family peace"),
        ("object", "Find objects"),
    ]
    for col, (goal_key, label) in zip(goal_cols, goal_buttons):
        with col:
            if st.button(label, use_container_width=True, type="primary" if st.session_state["setup_goal"] == goal_key else "secondary"):
                st.session_state["setup_goal"] = goal_key
                st.rerun()
    goal = _setup_goal_content(st.session_state["setup_goal"])
    _render_html(
        f"""
        <div class="goal-panel">
            <div>
                <span class="goal-label">Selected goal</span>
                <h3>{goal["title"]}</h3>
                <p>{goal["question"]}</p>
            </div>
            <div>
                <span class="goal-label">Nesto plan</span>
                <p>{goal["plan"]}</p>
            </div>
        </div>
        """,
    )

    _render_html('<div class="consent-card"><div><p class="section-title">Required documents</p><p class="muted">Read each document inside Nesto Care. The confirmation checkbox unlocks only after you mark that document as finished.</p></div>')
    all_checked = True
    for doc in LEGAL_DOCUMENTS:
        opened = st.session_state.get(f"opened_{doc['key']}", False)
        _render_html(
            f"""
            <div class="consent-row">
                <div>
                    <b>{doc["title"]}</b>
                    <span>{doc["summary"]}</span>
                </div>
            </div>
            """,
        )
        link_col, check_col = st.columns([1, 2.15])
        with link_col:
            if st.button(
                f"Read {doc['title']}",
                use_container_width=True,
                key=f"read_{doc['key']}",
            ):
                st.session_state["active_document"] = doc["key"]
                st.rerun()
        with check_col:
            checked = st.checkbox(
                f"{doc['title']} agreed.",
                key=f"accept_{doc['key']}",
                disabled=True,
            )
        all_checked = all_checked and checked and opened
    _render_html("</div>")
    _show_document_reader()

    _render_html(
        """
        <div class="data-note">
            <b>Safety boundary:</b> Nesto Care supports monitoring, reminders, family updates, and approved care scenarios only. It does not provide medical diagnosis, medication dosage advice, or emergency-service replacement.
        </div>
        """,
    )

    if st.button("Accept and continue to Nesto Care", type="primary", use_container_width=True, disabled=not all_checked):
        st.session_state["legal_accepted"] = True
        st.session_state["app_notice"] = {
            "title": "Consent accepted",
            "message": "Profile setup and required documents have been acknowledged.",
        }
        st.rerun()


def _clear_all_query_params():
    try:
        st.query_params.clear()
    except Exception:
        pass


def _route_authenticated_user(user, active_patient_id=""):
    session = auth_store.apply_user_session(st.session_state, user, active_patient_id)
    st.session_state.pop("_skip_cookie_restore", None)
    st.session_state.pop("login_error", None)
    st.session_state.pop("auth_notice", None)
    role = session.get("role")
    display_name = session.get("display_name") or session.get("username") or "Nesto user"
    route = ROLE_DEFAULT_ROUTE.get(role)
    if not route:
        st.session_state["login_error"] = "This account role is not supported yet."
        return False
    set_route(
        route.get("nav_role"),
        route.get("nav_page"),
        provider_tab=route.get("provider_tab"),
    )
    if role == "elderly_user":
        st.session_state["app_notice"] = {"title": "Signed in", "message": f"Welcome back, {display_name}."}
    elif role == "guardian_caregiver":
        st.session_state["app_notice"] = {"title": "Signed in", "message": f"Opening the Guardian / Caregiver dashboard for {display_name}."}
    elif role == "admin_provider":
        st.session_state["app_notice"] = {"title": "Signed in", "message": "Opening the provider dashboard."}
    st.session_state.pop("pending_login_user", None)
    st.session_state.pop("login_error", None)
    st.session_state.pop("auth_notice", None)
    _clear_query_params("auth_mode")
    return True


def _render_sign_in_page():
    apply_theme("light")
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] { display: none !important; }
            .block-container { max-width: 1260px !important; padding: 38px 18px !important; }
            .stApp { background: #f4efe5 !important; }
            div[data-testid="InputInstructions"] {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                min-height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            .signin-shell {
                border: 1px solid #e2d7c8;
                border-radius: 28px;
                background: linear-gradient(135deg, rgba(255,253,248,.97), rgba(244,239,229,.82));
                box-shadow: 0 24px 64px rgba(37,65,63,.11);
                padding: 18px;
                color: #123536;
                display: grid;
                grid-template-columns: .92fr 1.08fr;
                gap: 18px;
                align-items: stretch;
            }
            .signin-welcome,
            .signin-form-panel {
                border: 1px solid #e3d8c7;
                border-radius: 24px;
                background: rgba(255,253,248,.84);
                box-shadow: 0 14px 34px rgba(37,65,63,.06);
                position: relative;
                z-index: 1;
            }
            .signin-welcome {
                padding: 34px 30px;
                min-height: 490px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                background:
                    radial-gradient(circle at 80% 22%, rgba(127,169,140,.20), transparent 32%),
                    linear-gradient(145deg, rgba(255,253,248,.94), rgba(237,244,238,.78));
            }
            .signin-form-panel {
                padding: 34px;
                background: rgba(255,253,248,.94);
            }
            .signin-brand { display:flex; align-items:center; gap:12px; font-weight:950; font-size:1.15rem; color:#183f3a; }
            .signin-brand-mark { font-size:2.05rem; line-height:1; }
            .signin-kicker {
                display:inline-flex;
                align-items:center;
                gap:8px;
                width:fit-content;
                border:1px solid #cbdccb;
                border-radius:999px;
                background:#edf4ee;
                color:#176b4d;
                font-weight:950;
                font-size:.78rem;
                margin-bottom:14px;
                padding:7px 11px;
                letter-spacing:0;
            }
            .signin-shell h1 { margin:0 0 10px; font-size:clamp(2rem, 3vw, 3rem); line-height:1.05; letter-spacing:0; color:#183f3a; }
            .signin-form-panel h1 { font-size:clamp(1.8rem, 2.4vw, 2.35rem); }
            .signin-shell p { margin:0 0 18px; color:#60736f; font-weight:700; line-height:1.52; }
            div[data-testid="column"]:has(.signin-left-anchor) h1,
            div[data-testid="column"]:has(.signin-form-anchor) h1 {
                margin: 0 0 10px;
                font-size: clamp(2rem, 3vw, 3rem);
                line-height: 1.05;
                letter-spacing: 0;
                color: #183f3a;
            }
            div[data-testid="column"]:has(.signin-form-anchor) h1 {
                font-size: clamp(1.8rem, 2.4vw, 2.35rem);
            }
            div[data-testid="column"]:has(.signin-left-anchor) p,
            div[data-testid="column"]:has(.signin-form-anchor) p {
                margin: 0 0 18px;
                color: #60736f;
                font-weight: 700;
                line-height: 1.52;
            }
            .signin-error { border:1px solid #f4b4b4; background:#fff4f4; color:#8a1f1f; border-radius:14px; padding:12px 14px; font-weight:850; margin:10px 0 14px; }
            .signin-help { border:1px solid #dceadf; background:#f4fbf6; color:#31584d; border-radius:14px; padding:12px 14px; font-weight:750; margin-top:12px; }
            .signin-robot-stage {
                margin-top: 26px;
                min-height: 260px;
                display: grid;
                place-items: center;
                position: relative;
                pointer-events: none;
            }
            .signin-speech {
                position: absolute;
                top: 4px;
                right: 18px;
                max-width: 230px;
                border: 1px solid #e3d8c7;
                border-radius: 18px;
                background: rgba(255,253,248,.96);
                box-shadow: 0 12px 30px rgba(37,65,63,.08);
                color: #183f3a;
                font-weight: 950;
                line-height: 1.35;
                padding: 13px 15px;
                z-index: 2;
            }
            .signin-speech::after {
                content: "";
                position: absolute;
                right: 36px;
                bottom: -9px;
                width: 16px;
                height: 16px;
                background: rgba(255,253,248,.96);
                border-right: 1px solid #e3d8c7;
                border-bottom: 1px solid #e3d8c7;
                transform: rotate(45deg);
            }
            .signin-robot {
                border: 0;
                background: transparent;
                min-height: 230px;
                display: grid;
                place-items: center;
                text-align: center;
                padding: 22px 18px 0;
                pointer-events: none;
                cursor: default;
            }
            .signin-robot .nesto-bot {
                transform: scale(1.14);
                animation: nestoFloat 3s ease-in-out infinite;
                transform-origin: center bottom;
            }
            .signin-robot b { display:block; margin-top:18px; color:#183f3a; }
            .nesto-robot-illustration {
                pointer-events: none !important;
                cursor: default !important;
            }
            @keyframes nestoFloat {
                0%, 100% { transform: scale(1.14) translateY(0); }
                50% { transform: scale(1.14) translateY(-8px); }
            }
            .signin-role-list { display:grid; gap:10px; margin-top:18px; }
            .signin-role-list span { display:flex; align-items:center; gap:10px; border:1px solid #e3d8c7; border-radius:999px; background:rgba(255,253,248,.76); color:#183f3a; font-weight:850; padding:9px 12px; }
            .signin-secure-note { margin-top:16px; border:1px solid #cbdccb; border-radius:18px; background:#edf4ee; color:#31584d; padding:13px 14px; font-weight:800; line-height:1.42; }
            .signin-actions { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
            .signin-access-panel {
                margin-top: 18px;
                border: 1px solid #e3d8c7;
                border-radius: 24px;
                background: rgba(255,253,248,.9);
                box-shadow: 0 14px 34px rgba(37,65,63,.06);
                padding: 20px;
            }
            .signin-access-panel h2 {
                margin: 0 0 4px;
                color: #183f3a;
                font-size: 1.28rem;
                letter-spacing: 0;
            }
            .signin-access-panel p {
                margin: 0 0 14px;
                color: #60736f;
                font-weight: 750;
            }
            .signin-access-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(150px, 1fr));
                gap: 12px;
            }
            .signin-access-card,
            .signin-access-card:visited {
                min-height: 104px;
                border: 1px solid #e3d8c7;
                border-radius: 18px;
                background: rgba(255,253,248,.96);
                box-shadow: 0 10px 24px rgba(37,65,63,.05);
                color: #183f3a !important;
                display: flex;
                flex-direction: column;
                justify-content: center;
                gap: 8px;
                padding: 16px;
                text-decoration: none !important;
                font-weight: 950;
            }
            .signin-access-card:hover {
                border-color: #9fbdab;
                background: #f4fbf6;
                transform: translateY(-1px);
            }
            .signin-access-card span:first-child {
                width: 38px;
                height: 38px;
                border-radius: 14px;
                background: #edf4ee;
                display: inline-grid;
                place-items: center;
                font-size: 1.1rem;
            }
            .signin-access-card small {
                color: #60736f;
                font-weight: 800;
                line-height: 1.35;
            }
            .signin-divider {
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                gap: 12px;
                align-items: center;
                margin: 18px 0 14px;
                color: #7a8a84;
                font-weight: 850;
                font-size: .82rem;
            }
            .signin-divider::before,
            .signin-divider::after {
                content: "";
                height: 1px;
                background: #e3d8c7;
            }
            .signin-options-row {
                display:grid;
                grid-template-columns: 1fr auto;
                align-items:center;
                gap:14px;
                margin: 2px 0 16px;
            }
            .signin-options-row div[data-testid="stCheckbox"] {
                margin: 0 !important;
            }
            .signin-options-row div[data-testid="stCheckbox"] label {
                color:#31584d !important;
                font-weight:850 !important;
            }
            .signin-forgot-wrap {
                display:flex;
                align-items:center;
                justify-content:flex-end;
                min-height:38px;
            }
            .signin-forgot-button {
                color: #176b4d !important;
                font-weight: 900;
                text-decoration: none !important;
                display: inline-flex;
                align-items:center;
                justify-content:center;
                border:0;
                border-radius:999px;
                background:transparent;
                min-height:32px;
                padding:0 2px;
            }
            .signin-forgot-button:hover {
                color: #183f3a !important;
            }
            div[data-testid="stHorizontalBlock"]:has(.signin-left-anchor) {
                border: 1px solid #e2d7c8;
                border-radius: 28px;
                background: linear-gradient(135deg, rgba(255,253,248,.97), rgba(244,239,229,.82));
                box-shadow: 0 24px 64px rgba(37,65,63,.11);
                padding: 18px;
                color: #123536;
                gap: 18px !important;
                align-items: stretch;
            }
            div[data-testid="column"]:has(.signin-left-anchor),
            div[data-testid="column"]:has(.signin-form-anchor) {
                border: 1px solid #e3d8c7;
                border-radius: 24px;
                background: rgba(255,253,248,.9);
                box-shadow: 0 14px 34px rgba(37,65,63,.06);
                padding: 34px 30px;
                min-height: 640px;
            }
            div[data-testid="column"]:has(.signin-left-anchor) {
                background:
                    radial-gradient(circle at 80% 22%, rgba(127,169,140,.20), transparent 32%),
                    linear-gradient(145deg, rgba(255,253,248,.94), rgba(237,244,238,.78));
            }
            div[data-testid="column"]:has(.signin-form-anchor) {
                padding: 34px;
                background: rgba(255,253,248,.96);
            }
            div[data-testid="column"]:has(.signin-form-anchor) div[data-testid="stTextInput"] {
                margin-bottom: 12px;
            }
            div[data-testid="column"]:has(.signin-form-anchor) div[data-testid="stTextInput"] label,
            div[data-testid="column"]:has(.signin-form-anchor) div[data-testid="stTextInput"] label p {
                color:#183f3a !important;
                font-weight:900 !important;
                font-size:.92rem !important;
            }
            div[data-testid="column"]:has(.signin-form-anchor) div[data-testid="stTextInput"] input {
                min-height: 48px !important;
                border-radius: 16px !important;
                border: 1px solid #d8e4da !important;
                background: rgba(255,252,246,.96) !important;
                color: #183f3a !important;
                font-size: 15px !important;
                padding-left: 14px !important;
                box-shadow: none !important;
            }
            div[data-testid="column"]:has(.signin-form-anchor) div[data-testid="stTextInput"] input:focus {
                border-color:#7fa98c !important;
                box-shadow:0 0 0 3px rgba(127,169,140,.18) !important;
            }
            div[data-testid="stButton"] button {
                border-radius:999px !important;
                border:1px solid #e3d8c7 !important;
                background:#fffdf8 !important;
                color:#183f3a !important;
                font-weight:900 !important;
                min-height:46px !important;
            }
            div[data-testid="stButton"] button[kind="primary"],
            div[data-testid="stButton"] button[data-testid="baseButton-primary"],
            div[data-testid="stButton"] button[kind="primary"]:hover,
            div[data-testid="stButton"] button[data-testid="baseButton-primary"]:hover,
            div[data-testid="stButton"] button[kind="primary"]:focus,
            div[data-testid="stButton"] button[data-testid="baseButton-primary"]:focus {
                background: #176b4d !important;
                background-color: #176b4d !important;
                border-color: #176b4d !important;
                color: #fffdf8 !important;
                border-radius: 999px !important;
                box-shadow: 0 12px 24px rgba(23,107,77,.16) !important;
                font-weight: 950 !important;
            }
            div[data-testid="stButton"] button[kind="primary"] *,
            div[data-testid="stButton"] button[data-testid="baseButton-primary"] * {
                color: #fffdf8 !important;
            }
            @media (max-width: 820px) {
                .signin-shell { grid-template-columns: 1fr; }
                .signin-welcome { min-height: auto; }
                div[data-testid="stHorizontalBlock"]:has(.signin-left-anchor) {
                    display: block !important;
                }
                div[data-testid="column"]:has(.signin-left-anchor),
                div[data-testid="column"]:has(.signin-form-anchor) {
                    margin-bottom: 16px;
                    min-height: auto;
                }
                .signin-options-row { grid-template-columns: 1fr; }
                .signin-forgot-wrap { justify-content:flex-start; }
                .signin-speech { position:relative; top:auto; right:auto; margin-bottom:14px; }
                .signin-access-grid { grid-template-columns: 1fr; }
            }
        </style>
        """,
        unsafe_allow_html=True,
        )
    pending = st.session_state.get("pending_login_user")

    def _sync_visible_login_inputs():
        try:
            st.components.v1.html(
                """
                <script>
                const syncNestoLoginAutofill = () => {
                  try {
                    const doc = window.parent.document;
                    const inputs = Array.from(doc.querySelectorAll('input'));
                    inputs.forEach((input) => {
                      const type = (input.getAttribute('type') || '').toLowerCase();
                      if (type === 'text' || type === 'email') {
                        input.setAttribute('autocomplete', 'username');
                      }
                      if (type === 'password') {
                        input.setAttribute('autocomplete', 'current-password');
                      }
                      if ((type === 'text' || type === 'email' || type === 'password') && input.value) {
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                      }
                    });
                  } catch (error) {}
                };
                syncNestoLoginAutofill();
                window.setTimeout(syncNestoLoginAutofill, 300);
                window.setTimeout(syncNestoLoginAutofill, 900);
                </script>
                """,
                height=0,
            )
        except Exception:
            pass

    robot_markup = _sidebar_nesto_robot().replace(' style="transform:scale(.72);"', "")
    left_col, right_col = st.columns([0.92, 1.08], gap="medium")
    with left_col:
        _render_html(
            f"""
            <div class="signin-left-anchor"></div>
                <div>
                  <div class="signin-brand"><span class="signin-brand-mark">&#127968;</span><span>Nesto Care</span></div>
                  <h1>Welcome back to Nesto Care <span style="color:#7fa98c;">&#9829;</span></h1>
                  <p>Sign in to your account to continue managing care, connecting with loved ones, and keeping everyone safe.</p>
                  <div class="signin-role-list">
                    <span>&#9825; Personalized Care</span>
                    <span>&#128274; Secure & Private</span>
                    <span>&#128172; Stay Connected</span>
                  </div>
                </div>
                <div class="signin-robot-stage">
                  <div class="signin-speech">I'm Nesto. I'm here to help you. <span style="color:#7fa98c;">&#9829;</span></div>
                  <div class="signin-robot nesto-robot-card nesto-robot-illustration">
                    {robot_markup}
                    <b>Nesto is ready</b>
                    <span style="color:#176b4d;font-weight:900;">Secure sign-in</span>
                  </div>
                </div>
            """
        )
    with right_col:
        _render_html(
            """
                  <div id="signin-form" class="signin-form-anchor"></div>
                  <div class="signin-kicker">Secure sign-in</div>
                  <h1>Sign in to Nesto Care</h1>
                  <p>Use your account to continue to your dashboard.</p>
            """
        )
        if pending and pending.get("role") == "guardian_caregiver" and len(pending.get("linked_patients") or []) > 1:
            _render_html('<div class="signin-help">Select the care profile you want to open.</div>')
            options = pending.get("linked_patients") or []
            labels = [f"{item.get('patient_name')} ({item.get('preferred_name')})" for item in options]
            selected = st.radio("Assigned care profile", labels, label_visibility="collapsed")
            selected_index = labels.index(selected)
            if st.button("Continue", type="primary", use_container_width=True):
                patient_id = options[selected_index].get("patient_id", "")
                if _route_authenticated_user(pending, patient_id):
                    st.rerun()
        else:
            if st.session_state.get("login_error"):
                _render_html(f'<div class="signin-error">{st.session_state["login_error"]}</div>')
            identifier = st.text_input(
                "Email or username",
                placeholder="name@example.com",
                key="login_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password",
            )
            _sync_visible_login_inputs()
            opt_left, opt_right = st.columns([1, 1])
            with opt_left:
                st.checkbox("Remember me", key="remember_me")
            with opt_right:
                _render_html(
                    '<div class="signin-forgot-wrap"><a class="signin-forgot-button" href="?auth_mode=signin">Forgot password?</a></div>',
                )
            submitted = st.button("Sign in", type="primary", use_container_width=True, key="sign_in_button")
            if submitted:
                st.session_state.pop("login_error", None)
                st.session_state.pop("auth_notice", None)
                submitted_email = str(st.session_state.get("login_email") or identifier or "").strip().lower()
                submitted_password = str(st.session_state.get("login_password") or password or "")
                user, error = auth_store.authenticate_user(submitted_email, submitted_password)
                if error:
                    st.session_state["login_error"] = "We could not sign you in. Please check your email and password."
                    st.rerun()
                if user and user.get("role") == "guardian_caregiver" and len(user.get("linked_patients") or []) > 1:
                    st.session_state["pending_login_user"] = user
                    st.session_state.pop("login_error", None)
                    st.rerun()
                if user and _route_authenticated_user(user):
                    st.session_state.pop("login_error", None)
                    st.rerun()
            _render_html('<div class="signin-divider"><span>or</span></div>')
            col1, col2 = st.columns(2)
            if col1.button("Create a new profile", use_container_width=True):
                _clear_query_params("auth_mode")
                page_family.start_new_profile()
                st.rerun()
            if col2.button("Back to home", use_container_width=True):
                _clear_query_params("auth_mode")
                set_route("Product", "Landing Page")
                st.rerun()
            _render_html(
                '<div class="signin-secure-note">Your profile, care contacts, and dashboard access are protected by the same Nesto account flow.</div>',
            )
    _render_html(
        """
        <div class="signin-access-panel">
            <h2>Access your dashboard</h2>
            <p>Choose your role after signing in. These shortcuts keep you on the secure sign-in page.</p>
            <div class="signin-access-grid">
                <a class="signin-access-card" href="#signin-form"><span>&#9825;</span><b>Elderly User</b><small>Please sign in first.</small></a>
                <a class="signin-access-card" href="#signin-form"><span>&#128737;</span><b>Guardian / Caregiver</b><small>Please sign in first.</small></a>
                <a class="signin-access-card" href="#signin-form"><span>&#9881;</span><b>Admin / Provider</b><small>Please sign in first.</small></a>
                <a class="signin-access-card" href="#signin-form"><span>&#129302;</span><b>Nesto Robot</b><small>Please sign in first.</small></a>
            </div>
        </div>
        """
    )

def main():
    if _query_param("logout") == "1":
        logout_user()
    if st.session_state.pop("_clear_session_cookie", False):
        _clear_session_cookie_script()
    else:
        _restore_session_from_cookie()
    if _query_param("auth_mode") == "signin" and not _has_active_session():
        _render_sign_in_page()
        _render_build_marker()
        return
    if _query_param("auth_mode") == "signin" and _has_active_session():
        _clear_query_params("auth_mode")
    _consume_navigation_query()
    _write_session_cookie_script()
    _render_pending_notice()
    _render_build_marker()
    view = sidebar()
    page = PAGES[view]
    apply_theme(page["theme"])
    page["render"]()


if __name__ == "__main__":
    main()
