"""
Shared NESTO Care design system, CSS helpers, robot styling, and brand pattern.
"""

import streamlit as st


CORAL = "#6fa7a6"
PEACH = "#e6d7bf"
PURPLE = "#6fa7a6"
GREEN = "#7fa98c"
AMBER = "#f59e0b"
BLUE = "#8fa3b2"
RED = "#ff453a"
INK = "#25413f"
MUTED = "#6f7d7b"


def apply_theme(mode="light"):
    dark = mode == "dark"
    bg = "#202632" if dark else "#f4efe5"
    panel = "#303746" if dark else "#ffffff"
    text = "#f8fafc" if dark else INK
    muted = "#aab2c2" if dark else MUTED
    border = "#3e4656" if dark else "#e3d8c7"
    sidebar = "#232a36" if dark else "#ffffff"

    st.markdown(
        f"""
        <style>
        #MainMenu, footer, header {{ visibility:hidden; }}
        :root {{
            --nesto-bg: {bg};
            --nesto-panel: {panel};
            --nesto-surface: #fffdf8;
            --nesto-card: rgba(255, 253, 248, .88);
            --nesto-ink: #183f3a;
            --nesto-muted: #61716d;
            --nesto-border: #e3d8c7;
            --nesto-border-strong: #cbdccb;
            --nesto-green: #176b4d;
            --nesto-sage: #7fa98c;
            --nesto-mint: #edf4ee;
            --nesto-teal: #6fa7a6;
            --nesto-bluegray: #8fa3b2;
            --nesto-sand: #e6d7bf;
            --nesto-warning: #f59e0b;
            --nesto-danger: #ef4444;
            --nesto-radius: 22px;
            --nesto-shadow: 0 18px 42px rgba(37, 65, 63, .08);
            --nesto-brand-pattern: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150' fill='none'%3E%3Cg stroke-linecap='round' stroke-linejoin='round' stroke-width='2.6'%3E%3Cpath d='M23 42 36 31l13 11v19H27V45' stroke='%23A8BFAE'/%3E%3Cpath d='M35 61V49h8v12' stroke='%23A8BFAE'/%3E%3Cpath d='M95 30c5-8 18-2 14 8-2 7-10 12-14 16-5-4-13-9-15-16-4-10 9-16 15-8Z' stroke='%236FA7A6'/%3E%3Cpath d='M30 103c13-4 23-13 28-25 5 15-3 29-17 35-7 3-15 2-20-1 2-4 5-7 9-9Z' stroke='%238FA3B2'/%3E%3Cpath d='M43 94c-6 4-11 9-15 16' stroke='%238FA3B2'/%3E%3Cpath d='M105 91l20 8v12c0 13-9 22-20 27-11-5-20-14-20-27V99l20-8Z' stroke='%23E6D7BF'/%3E%3Cpath d='m96 114 7 7 14-16' stroke='%23A8BFAE'/%3E%3Cpath d='M129 48h10M134 43v10' stroke='%23E6D7BF'/%3E%3Ccircle cx='68' cy='126' r='5' stroke='%236FA7A6'/%3E%3C/g%3E%3C/svg%3E");
        }}
        .nesto-brand-pattern,
        .nesto-pattern-surface {{
            position:relative;
            overflow:hidden;
        }}
        .nesto-brand-pattern::before,
        .nesto-pattern-surface::before {{
            content:"";
            position:absolute;
            inset:0;
            background-image:var(--nesto-brand-pattern);
            background-size:150px 150px;
            background-repeat:repeat;
            opacity:.085;
            pointer-events:none;
            z-index:0;
        }}
        .nesto-pattern-soft::before {{ opacity:.06; }}
        .nesto-brand-pattern > *,
        .nesto-pattern-surface > * {{
            position:relative;
            z-index:1;
        }}
        .stApp::before {{
            content:"";
            position:fixed;
            inset:0;
            background-image:var(--nesto-brand-pattern);
            background-size:170px 170px;
            background-repeat:repeat;
            opacity:.045;
            pointer-events:none;
            z-index:0;
        }}
        .stApp > * {{
            position:relative;
            z-index:1;
        }}
        .nesto-page-shell {{
            max-width: 1240px;
            margin: 0 auto;
            color: var(--nesto-ink);
        }}
        .nesto-card,
        .nesto-dashboard-card {{
            border: 1px solid var(--nesto-border);
            border-radius: var(--nesto-radius);
            background: var(--nesto-card);
            box-shadow: var(--nesto-shadow);
            backdrop-filter: blur(12px);
        }}
        .nesto-primary-control,
        .nesto-secondary-control,
        .nesto-status-pill {{
            min-height: 42px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 16px;
            font-weight: 900;
            letter-spacing: 0;
            text-decoration: none !important;
            box-sizing: border-box;
        }}
        .nesto-primary-control {{
            background: var(--nesto-green);
            border: 1px solid var(--nesto-green);
            color: #fffdf8 !important;
            box-shadow: 0 12px 28px rgba(23, 107, 77, .18);
        }}
        .nesto-secondary-control,
        .nesto-status-pill {{
            background: rgba(255, 253, 248, .9);
            border: 1px solid var(--nesto-border);
            color: var(--nesto-ink) !important;
            box-shadow: 0 10px 24px rgba(37, 65, 63, .06);
        }}
        :where(.signin-shell, .cg-page, .task9-admin, .nesto-page-shell) a {{
            text-decoration: none !important;
            text-decoration-line: none !important;
        }}
        .nesto-table {{
            width: 100%;
            border-collapse: collapse;
            color: var(--nesto-ink);
        }}
        .nesto-table th {{
            color: var(--nesto-muted);
            text-align: left;
            font-size: .76rem;
            font-weight: 950;
            padding: 0 10px 10px 0;
        }}
        .nesto-table td {{
            border-top: 1px solid #eee6da;
            padding: 11px 10px 11px 0;
            color: #324a48;
            font-weight: 750;
            vertical-align: top;
        }}
        .stTextInput input,
        .stTextArea textarea,
        div[data-baseweb="select"] > div {{
            border-radius: 14px !important;
            border-color: rgba(168, 191, 174, .52) !important;
            background: rgba(255, 252, 246, .92) !important;
            color: var(--nesto-ink) !important;
            box-shadow: none !important;
        }}
        .stCheckbox label,
        .stTextInput label,
        .stTextArea label {{
            color: var(--nesto-ink) !important;
            font-weight: 800 !important;
        }}
        .stApp {{ background:{bg}; }}
        .block-container {{ max-width:1220px; padding-top:2.1rem; padding-bottom:3rem; }}
        html, body, [class*="css"] {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
        section[data-testid="stSidebar"] {{ background:{sidebar}; border-right:1px solid {border}; }}
        section[data-testid="stSidebar"] * {{ color:{text}; }}
        section[data-testid="stSidebar"] .stRadio label {{ font-weight:750; }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{ background:#ffffff !important; border:1px solid #e3d8c7 !important; color:#25413f !important; }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{ color:#25413f !important; }}
        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{ color:#25413f !important; fill:#25413f !important; }}
        section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p {{ color:{text} !important; }}

        .topbar {{ display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:22px; }}
        .kicker {{ color:{CORAL}; font-size:.72rem; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
        .title {{ color:{text}; font-size:2rem; line-height:1.08; font-weight:900; margin:5px 0; }}
        .subtitle {{ color:{muted}; font-size:1rem; margin:0; line-height:1.45; }}
        .pill {{ display:inline-flex; align-items:center; gap:8px; border-radius:999px; padding:8px 13px; background:{panel}; border:1px solid {border}; color:{text}; font-weight:800; box-shadow:0 3px 10px rgba(0,0,0,.08); }}

        .card {{ background:{panel}; border:1px solid {border}; border-radius:14px; padding:20px; box-shadow:0 1px 2px rgba(0,0,0,.08); margin-bottom:16px; }}
        .section-title {{ color:{text}; font-weight:900; font-size:1.05rem; margin:0 0 12px 0; }}
        .muted {{ color:{muted}; line-height:1.5; }}
        .row {{ display:flex; align-items:center; gap:12px; padding:11px 0; border-bottom:1px solid {border}; }}
        .row:last-child {{ border-bottom:0; }}
        .row-main {{ color:{text}; font-weight:700; }}
        .row-sub {{ color:{muted}; font-size:.86rem; }}
        .time {{ color:{muted}; font-size:.82rem; min-width:52px; }}
        .dot {{ width:9px; height:9px; border-radius:999px; flex:0 0 auto; }}
        .badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:4px 10px; font-size:.72rem; font-weight:900; margin-left:auto; }}
        .badge-green {{ background:#e9f2ec; color:{GREEN}; }}
        .badge-purple {{ background:#e7f0ef; color:{PURPLE}; }}
        .badge-amber {{ background:#fff3dc; color:{AMBER}; }}
        .badge-red {{ background:#ffe2e2; color:{RED}; }}
        .badge-gray {{ background:#f2f0f4; color:{MUTED}; }}

        .metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(140px,1fr)); gap:14px; }}
        .metric {{ background:{panel}; border:1px solid {border}; border-radius:14px; padding:18px; min-height:128px; box-shadow:0 1px 2px rgba(0,0,0,.06); }}
        .metric-label {{ color:{muted}; font-size:.72rem; font-weight:900; text-transform:uppercase; letter-spacing:.05em; }}
        .metric-value {{ color:{text}; font-size:1.8rem; font-weight:950; margin-top:8px; }}

        .phone-grid {{ display:grid; grid-template-columns:repeat(2,minmax(260px,1fr)); gap:18px; }}
        .phone {{ background:#fff; color:{INK}; border:1px solid #dddfe2; border-radius:26px; padding:18px; min-height:590px; box-shadow:0 8px 24px rgba(0,0,0,.12); }}
        .phone-title {{ color:{INK}; font-size:1.35rem; font-weight:950; line-height:1.16; margin:0 0 6px 0; }}
        .phone-sub {{ color:{MUTED}; font-size:.84rem; line-height:1.45; margin:0; }}
        .phone-card {{ border:1px solid #dddfe2; border-radius:16px; padding:16px; margin-top:14px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.06); }}
        .phone-nav {{ display:grid; grid-template-columns:repeat(5,1fr); gap:4px; border-top:1px solid #dddfe2; margin-top:16px; padding-top:12px; text-align:center; color:{PURPLE}; font-size:.7rem; font-weight:900; }}
        .robot-home-setting {{ position:relative; overflow:hidden; border-radius:38px; padding:52px 42px 44px; margin-bottom:22px; min-height:760px; background:linear-gradient(180deg,#f3dfc2 0%,#efe2cf 44%,#c8935f 45%,#d0a06e 100%); box-shadow:0 28px 72px rgba(37,65,63,.16); border:1px solid #e3d8c7; }}
        .robot-home-setting:before {{ content:""; position:absolute; inset:0; background:linear-gradient(90deg,rgba(255,255,255,.25),transparent 26%,transparent 74%,rgba(255,255,255,.18)); pointer-events:none; }}
        .home-ambient {{ position:absolute; pointer-events:none; opacity:.72; }}
        .home-ambient.lamp {{ left:34px; top:72px; width:90px; height:210px; border-radius:45px 45px 10px 10px; background:linear-gradient(180deg,#fff3d7,#d6ac73 58%,#8f6e48 59%); box-shadow:0 0 64px rgba(255,230,180,.5); }}
        .home-ambient.lamp:after {{ content:""; position:absolute; left:32px; bottom:-80px; width:28px; height:86px; background:#85684a; border-radius:999px; }}
        .home-ambient.plant {{ right:36px; top:74px; width:150px; height:230px; background:linear-gradient(135deg,transparent 0 28%,rgba(127,169,140,.55) 29% 38%,transparent 39%), linear-gradient(35deg,transparent 0 44%,rgba(95,137,100,.5) 45% 55%,transparent 56%); border-radius:40px; }}
        .home-ambient.shelf {{ right:170px; top:92px; width:190px; height:12px; background:#b99263; border-radius:999px; box-shadow:0 54px 0 rgba(185,146,99,.72); }}
        .home-table-base {{ position:absolute; left:18%; right:18%; bottom:20px; height:34px; border-radius:999px; background:linear-gradient(90deg,#b78352,#edc797,#b78352); box-shadow:0 14px 28px rgba(37,65,63,.18); }}
        .robot-tablet-frame {{ position:relative; z-index:1; background:#111; border-radius:48px; padding:26px; box-shadow:0 30px 74px rgba(20,28,25,.34), inset 0 0 0 1px rgba(255,255,255,.16); max-width:1320px; margin:0 auto; }}
        .robot-tablet-frame:before {{ content:""; position:absolute; top:10px; left:50%; transform:translateX(-50%); width:22px; height:22px; border-radius:50%; background:#1f2937; box-shadow:inset 0 0 0 5px #0b1017; z-index:3; }}
        .robot-tablet {{ position:relative; overflow:hidden; min-height:650px; border-radius:30px; background:radial-gradient(circle at 80% 16%, rgba(127,169,140,.22), transparent 31%), linear-gradient(135deg,#fffdf8 0%,#fbf5ea 58%,#f8efe5 100%); border:1px solid #eadfcd; padding:42px; }}
        .tablet-brand-row {{ display:flex; align-items:center; gap:12px; position:relative; z-index:2; color:{INK}; }}
        .tablet-brand-row b {{ display:block; font-size:1.02rem; font-weight:950; }}
        .tablet-brand-row span {{ display:block; color:{MUTED}; font-size:.82rem; margin-top:2px; }}
        .tablet-brand-mark {{ width:42px; height:42px; border-radius:14px; background:#e9f2ec; border:1px solid #cbdccb; color:{GREEN}; display:grid; place-items:center; font-size:1.2rem; }}
        .tablet-status {{ position:absolute; top:42px; right:42px; display:flex; gap:14px; align-items:center; color:{INK}; font-weight:850; z-index:2; }}
        .tablet-time {{ display:flex; align-items:center; gap:8px; border:1px solid #e3d8c7; background:rgba(255,255,255,.84); border-radius:999px; padding:10px 18px; box-shadow:0 8px 20px rgba(37,65,63,.09); }}
        .tablet-time span {{ font-weight:650; color:#6f7d7b; font-size:.85rem; }}
        .tablet-wifi {{ font-size:1.75rem; color:{GREEN}; }}
        .tablet-hero {{ display:grid; grid-template-columns:1.05fr .95fr; gap:30px; align-items:start; margin:26px 0 30px; }}
        .tablet-greeting {{ color:{INK}; font-size:2.25rem; font-weight:500; line-height:1.1; margin-top:6px; }}
        .tablet-name {{ display:flex; align-items:center; gap:18px; font-size:4.9rem; font-weight:950; letter-spacing:0; margin-top:8px; }}
        .tablet-sun {{ width:62px; height:62px; border-radius:50%; background:#f0a516; display:inline-block; box-shadow:0 0 0 12px rgba(240,165,22,.16); }}
        .tablet-copy {{ color:#3e4e4b; font-size:1.3rem; line-height:1.48; max-width:520px; margin-top:18px; }}
        .tablet-care-chips {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }}
        .tablet-care-chips span {{ border:1px solid #cbdccb; background:#edf4ee; color:{INK}; border-radius:999px; padding:7px 11px; font-size:.78rem; font-weight:900; }}
        .tablet-bot-zone {{ display:flex; justify-content:flex-end; align-items:center; gap:18px; min-height:230px; padding-right:26px; }}
        .speech-bubble {{ background:rgba(255,255,255,.9); border:1px solid #e3d8c7; border-radius:22px; padding:18px 20px; color:{INK}; font-size:1.2rem; line-height:1.4; box-shadow:0 12px 28px rgba(37,65,63,.1); position:relative; max-width:230px; }}
        .speech-bubble:after {{ content:""; position:absolute; right:-14px; bottom:22px; width:24px; height:24px; background:rgba(255,255,255,.86); border-right:1px solid #e3d8c7; border-bottom:1px solid #e3d8c7; transform:rotate(-35deg); }}
        .tablet-bot-zone .nesto-bot {{ transform:scale(1.55); margin-right:34px; }}
        .tablet-actions-grid {{ display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)); gap:20px; position:relative; z-index:2; padding-bottom:36px; }}
        .tablet-action-card {{ min-height:178px; border-radius:24px; border:1px solid #e3d8c7; background:rgba(255,255,255,.78); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:13px; box-shadow:0 12px 28px rgba(37,65,63,.09); text-align:center; text-decoration:none !important; color:inherit !important; cursor:pointer; transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease; padding:18px; }}
        .tablet-action-card:hover {{ transform:translateY(-4px); box-shadow:0 18px 34px rgba(37,65,63,.14); border-color:#7fa98c; }}
        .tablet-action-card.active {{ border-color:#7fa98c; box-shadow:0 0 0 4px rgba(127,169,140,.18), 0 18px 34px rgba(37,65,63,.14); }}
        .tablet-action-card.blue {{ background:linear-gradient(135deg,#ffffff,#eef4f5); }}
        .tablet-action-card.purple {{ background:linear-gradient(135deg,#ffffff,#f3eef7); }}
        .tablet-action-card.amber {{ background:linear-gradient(135deg,#ffffff,#fff5df); }}
        .tablet-action-card.red {{ background:linear-gradient(135deg,#fff7f7,#ffecec); border-color:#f7caca; }}
        .tablet-icon {{ width:82px; height:82px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:2.35rem; background:#edf4ee; color:{INK}; }}
        .tablet-action-title {{ font-size:1.45rem; font-weight:950; color:{INK}; }}
        .tablet-action-copy span {{ display:block; color:{MUTED}; font-size:.82rem; line-height:1.28; max-width:210px; margin:7px auto 0; }}
        .tablet-action-card.red .tablet-action-title {{ color:{RED}; }}
        .tablet-settings {{ display:inline-flex; align-items:center; gap:10px; position:absolute; bottom:20px; left:50%; transform:translateX(-50%); border:1px solid #e3d8c7; background:rgba(255,255,255,.9); border-radius:999px; padding:12px 24px; color:{INK}; font-weight:900; box-shadow:0 8px 22px rgba(37,65,63,.1); }}
        .action-panel {{ display:grid; grid-template-columns:1.3fr .7fr; gap:16px; border:1px solid #cbdccb; border-radius:22px; background:linear-gradient(135deg,#edf4ee,#fffdf8); padding:20px; margin:18px 0; box-shadow:0 12px 28px rgba(37,65,63,.08); }}
        .action-panel-main h3 {{ margin:4px 0 8px; color:{INK}; font-size:1.55rem; font-weight:950; }}
        .action-panel-main p {{ color:#3e4e4b; line-height:1.5; margin:0; }}
        .action-panel-side {{ border:1px solid #e3d8c7; border-radius:18px; background:#fffdf8; padding:16px; display:flex; flex-direction:column; justify-content:center; gap:8px; }}
        .action-panel-side b {{ color:{INK}; }}
        .action-panel-side span {{ color:{MUTED}; line-height:1.45; }}
        .care-action-hub {{ display:grid; grid-template-columns:.72fr 1.28fr; gap:16px; border:1px solid #e3d8c7; border-radius:24px; background:#fffdf8; padding:22px; margin:18px 0; box-shadow:0 12px 30px rgba(37,65,63,.08); }}
        .care-action-intro {{ border-radius:20px; background:linear-gradient(135deg,#edf4ee,#f8efe2); border:1px solid #d9d0bd; padding:20px; display:flex; flex-direction:column; justify-content:center; }}
        .care-action-intro h3 {{ color:{INK}; font-size:1.55rem; line-height:1.18; margin:6px 0 10px; font-weight:950; }}
        .care-action-intro p {{ color:#3e4e4b; line-height:1.5; margin:0; }}
        .care-action-grid {{ display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)); gap:12px; }}
        .care-action-card {{ display:flex; align-items:center; gap:14px; min-height:116px; border:1px solid #e3d8c7; border-radius:18px; background:#ffffff; padding:16px; text-decoration:none !important; color:{INK} !important; box-shadow:0 4px 14px rgba(37,65,63,.06); transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease; }}
        .care-action-card:hover {{ transform:translateY(-3px); border-color:{GREEN}; box-shadow:0 12px 26px rgba(37,65,63,.12); }}
        .care-action-card.active {{ border-color:{GREEN}; background:#edf4ee; box-shadow:0 0 0 4px rgba(127,169,140,.18); }}
        .care-action-card.emergency {{ background:#fff7f7; border-color:#f7caca; }}
        .care-action-icon {{ width:58px; height:58px; flex:0 0 auto; border-radius:18px; display:grid; place-items:center; background:#e9f2ec; color:{INK}; font-size:1.72rem; }}
        .care-action-card.emergency .care-action-icon {{ background:#ffe2e2; color:{RED}; }}
        .care-action-card b {{ display:block; color:{INK}; font-size:1rem; line-height:1.2; margin-bottom:5px; }}
        .care-action-card span {{ display:block; color:{MUTED}; font-size:.82rem; line-height:1.36; }}
        .activity-feed {{ display:grid; gap:10px; margin-top:12px; }}
        .activity-row {{ display:flex; align-items:center; gap:13px; border:1px solid #eadfcd; background:#fffdf8; border-radius:16px; padding:12px 14px; }}
        .activity-icon {{ width:44px; height:44px; border-radius:15px; display:grid; place-items:center; background:#edf4ee; font-size:1.35rem; flex:0 0 auto; }}
        .activity-row b {{ display:block; color:{INK}; font-weight:900; line-height:1.3; }}
        .activity-row span {{ display:block; color:{MUTED}; font-size:.82rem; margin-top:3px; }}
        .activity-row.medicine .activity-icon {{ background:#eef4f5; }}
        .activity-row.call .activity-icon {{ background:#f3eef7; }}
        .activity-row.mood .activity-icon {{ background:#fff5df; }}
        .activity-row.emergency .activity-icon {{ background:#ffe2e2; color:{RED}; }}
        .activity-row.object .activity-icon {{ background:#edf4ee; color:{GREEN}; }}
        .family-action-hub {{ display:grid; grid-template-columns:.65fr 1.35fr; gap:16px; border:1px solid #e3d8c7; border-radius:24px; background:#fffdf8; padding:22px; margin:18px 0; box-shadow:0 12px 30px rgba(37,65,63,.08); }}
        .family-action-hub h3 {{ color:{INK}; font-size:1.55rem; line-height:1.18; margin:6px 0 10px; font-weight:950; }}
        .family-action-hub p {{ color:#3e4e4b; line-height:1.5; margin:0; }}
        .family-action-grid {{ display:grid; grid-template-columns:repeat(4,minmax(135px,1fr)); gap:12px; }}
        .family-action-card {{ display:flex; flex-direction:column; justify-content:center; gap:10px; min-height:142px; border:1px solid #e3d8c7; border-radius:18px; background:#ffffff; padding:16px; text-decoration:none !important; color:{INK} !important; box-shadow:0 4px 14px rgba(37,65,63,.06); transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease; }}
        .family-action-card:hover {{ transform:translateY(-3px); border-color:{GREEN}; box-shadow:0 12px 26px rgba(37,65,63,.12); }}
        .family-action-card.active {{ border-color:{GREEN}; background:#edf4ee; box-shadow:0 0 0 4px rgba(127,169,140,.18); }}
        .family-action-icon {{ width:54px; height:54px; flex:0 0 auto; border-radius:18px; display:grid; place-items:center; background:#e9f2ec; color:{INK}; font-size:1.55rem; }}
        .family-action-card b {{ display:block; color:{INK}; font-size:.98rem; line-height:1.2; }}
        .family-action-card span {{ display:block; color:{MUTED}; font-size:.8rem; line-height:1.34; }}
        .family-landing {{ color:{INK}; }}
        .family-landing-nav {{ display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:28px; margin-bottom:26px; }}
        .family-brand {{ display:flex; align-items:center; gap:12px; color:{INK}; font-size:1.8rem; font-weight:950; }}
        .family-brand-icon {{ width:46px; height:46px; border:2px solid {GREEN}; border-radius:14px; display:grid; place-items:center; color:{GREEN}; background:rgba(255,255,255,.62); font-size:1.35rem; }}
        .family-brand em {{ color:#ad8c55; font-family:Georgia,serif; font-weight:500; font-style:italic; margin-left:2px; }}
        .family-nav-links {{ display:flex; justify-content:center; align-items:center; gap:34px; }}
        .family-nav-links a {{ color:{INK} !important; text-decoration:none !important; font-weight:760; border-bottom:2px solid transparent; padding:8px 0; }}
        .family-nav-links a:hover {{ border-bottom-color:{GREEN}; }}
        .family-download {{ justify-self:end; border-radius:10px; padding:14px 20px; background:{GREEN}; color:#fff !important; text-decoration:none !important; font-weight:900; box-shadow:0 12px 26px rgba(37,65,63,.16); }}
        .family-hero {{ display:grid; grid-template-columns:.92fr 1.08fr; align-items:center; gap:42px; margin-bottom:28px; }}
        .family-pill {{ display:inline-flex; align-items:center; border-radius:999px; background:#e9f2ec; color:{INK}; padding:8px 14px; font-size:.78rem; text-transform:uppercase; font-weight:950; letter-spacing:.06em; }}
        .family-copy h1 {{ color:{INK}; font-family:Georgia,serif; font-size:4.25rem; line-height:1.05; letter-spacing:0; margin:18px 0 22px; font-weight:800; }}
        .family-copy p {{ color:#3e4e4b; font-size:1.08rem; line-height:1.65; max-width:620px; margin:0; }}
        .family-benefits {{ display:grid; grid-template-columns:repeat(3,1fr); gap:18px; margin:30px 0; }}
        .family-benefits div {{ display:grid; grid-template-columns:50px 1fr; gap:12px; align-items:center; }}
        .family-benefits span {{ grid-row:span 2; width:50px; height:50px; border-radius:50%; display:grid; place-items:center; background:#dfe9dc; color:{GREEN}; font-size:1.45rem; }}
        .family-benefits b {{ color:{INK}; font-size:.95rem; }}
        .family-benefits em {{ color:{MUTED}; font-size:.84rem; line-height:1.35; font-style:normal; }}
        .family-cta-row {{ display:flex; gap:14px; flex-wrap:wrap; margin-bottom:18px; }}
        .family-cta-row a {{ display:inline-flex; align-items:center; justify-content:center; min-height:52px; min-width:210px; border-radius:10px; padding:13px 22px; background:{GREEN}; color:#fff !important; text-decoration:none !important; font-weight:900; border:1px solid {GREEN}; box-shadow:0 12px 24px rgba(37,65,63,.14); }}
        .family-cta-row a.secondary {{ background:#fffdf8; color:{INK} !important; border-color:{GREEN}; box-shadow:none; }}
        .family-secure-line {{ color:{INK}; font-weight:760; display:flex; align-items:center; gap:8px; }}
        .family-phone-showcase {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; align-items:start; }}
        .landing-phone {{ background:#fffdf8; color:{INK}; border:10px solid #161616; border-radius:38px; padding:18px; min-height:620px; box-shadow:0 18px 44px rgba(37,65,63,.18); }}
        .landing-phone.second {{ margin-top:18px; }}
        .phone-top {{ display:flex; justify-content:space-between; align-items:center; font-weight:950; color:{INK}; margin-bottom:18px; }}
        .landing-phone-brand {{ display:flex; align-items:center; gap:8px; margin-bottom:16px; color:{INK}; font-size:1.25rem; font-weight:950; }}
        .landing-phone-brand span {{ width:28px; height:28px; border-radius:9px; background:#e9f2ec; display:grid; place-items:center; color:{GREEN}; }}
        .landing-status-card {{ display:grid; grid-template-columns:54px 1fr 72px; gap:12px; align-items:center; background:#fff; border:1px solid #eadfcd; border-radius:18px; padding:14px; margin:14px 0; box-shadow:0 4px 16px rgba(37,65,63,.08); }}
        .landing-status-card b, .landing-summary-card b, .landing-list-card b {{ color:{INK}; font-weight:950; }}
        .landing-status-card em, .landing-status-card small {{ display:block; color:{MUTED}; font-style:normal; line-height:1.4; }}
        .status-check {{ width:48px; height:48px; border-radius:50%; background:{GREEN}; color:#fff; display:grid; place-items:center; font-size:1.4rem; font-weight:950; }}
        .patient-photo {{ width:68px; height:68px; border-radius:50%; border:3px solid #9bc3a5; background:#f8efe5; display:grid; place-items:center; font-size:2rem; }}
        .landing-summary-card, .landing-list-card {{ position:relative; background:#fff; border:1px solid #eadfcd; border-radius:18px; padding:14px; margin-bottom:14px; box-shadow:0 4px 16px rgba(37,65,63,.08); overflow:hidden; }}
        .landing-summary-card > div:first-child, .landing-list-card > div:first-child {{ display:flex; justify-content:space-between; gap:10px; }}
        .landing-summary-card a, .landing-list-card a {{ color:{GREEN}; font-weight:900; text-decoration:none; }}
        .landing-summary-card p {{ color:{INK}; line-height:1.45; max-width:72%; margin:12px 0 6px; }}
        .landing-bot-small {{ position:absolute; right:12px; bottom:4px; transform:scale(.55); transform-origin:bottom right; width:92px; height:116px; }}
        .landing-mini-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:12px; }}
        .landing-mini-stat {{ min-height:128px; background:#fff; border:1px solid #eadfcd; border-radius:14px; padding:10px; box-shadow:0 2px 9px rgba(37,65,63,.05); }}
        .landing-mini-stat span {{ display:block; font-size:1.25rem; }}
        .landing-mini-stat b {{ display:block; color:{INK}; font-size:.73rem; margin-top:6px; }}
        .landing-mini-stat strong {{ display:block; color:{INK}; font-size:1.08rem; line-height:1.1; margin-top:8px; }}
        .landing-mini-stat small, .landing-mini-stat em {{ display:block; color:{MUTED}; font-size:.7rem; font-style:normal; margin-top:3px; }}
        .landing-mini-stat em {{ color:{GREEN}; }}
        .landing-tabs {{ display:grid; grid-template-columns:repeat(4,1fr); gap:4px; background:#f4efe5; border-radius:999px; padding:5px; margin:14px 0; text-align:center; font-size:.76rem; }}
        .landing-tabs span, .landing-tabs b {{ padding:8px 6px; border-radius:999px; color:{MUTED}; }}
        .landing-tabs b {{ background:{GREEN}; color:#fff; }}
        .landing-health-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }}
        .landing-health-card {{ background:#fff; border:1px solid #eadfcd; border-radius:16px; padding:12px; color:{GREEN}; box-shadow:0 2px 10px rgba(37,65,63,.06); }}
        .landing-health-card.blue {{ color:#4f83ad; }}
        .landing-health-card.amber {{ color:{AMBER}; }}
        .landing-health-card span {{ font-size:1.15rem; }}
        .landing-health-card b, .landing-health-card strong, .landing-health-card em {{ display:block; }}
        .landing-health-card b {{ color:{INK}; font-size:.78rem; margin-top:5px; }}
        .landing-health-card strong {{ color:{INK}; font-size:1rem; margin-top:6px; }}
        .landing-health-card em {{ color:{GREEN}; font-size:.74rem; font-style:normal; margin:3px 0 8px; }}
        .landing-alert-row {{ display:grid; grid-template-columns:34px 1fr auto; gap:10px; align-items:center; border-top:1px solid #eadfcd; padding:10px 0; }}
        .landing-alert-row span {{ width:30px; height:30px; border-radius:50%; display:grid; place-items:center; background:#ffe7e3; color:{RED}; }}
        .landing-alert-row em {{ font-style:normal; border-radius:999px; padding:5px 9px; background:#ffe2e2; color:{RED}; font-size:.7rem; font-weight:900; }}
        .landing-contact {{ text-align:center; border:1px solid #f7caca; color:{RED}; border-radius:999px; padding:12px; font-weight:950; background:#fff7f7; margin-top:12px; }}
        .family-feature-panel {{ border:1px solid #e3d8c7; background:rgba(255,255,255,.62); border-radius:28px; padding:28px; margin:24px 0 16px; box-shadow:0 14px 36px rgba(37,65,63,.08); }}
        .family-feature-panel h2, .family-how-panel h2 {{ color:{INK}; font-family:Georgia,serif; text-align:center; margin:0 0 22px; font-size:1.85rem; }}
        .family-feature-grid {{ display:grid; grid-template-columns:repeat(4,minmax(150px,1fr)); gap:12px; }}
        .family-feature-card {{ background:#fffdf8; border:1px solid #eadfcd; border-radius:16px; padding:18px 12px; min-height:150px; text-align:center; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .family-feature-card div {{ font-size:2rem; min-height:42px; }}
        .family-feature-card b {{ display:block; color:{INK}; margin:8px 0 6px; }}
        .family-feature-card p {{ color:{MUTED}; font-size:.82rem; line-height:1.35; margin:0; }}
        .family-how-panel {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; align-items:center; border:1px solid #e3d8c7; border-radius:24px; padding:24px; margin-bottom:16px; background:#fffdf8; }}
        .family-how-panel h2 {{ text-align:left; margin:8px 0 10px; }}
        .family-how-panel p {{ color:{MUTED}; line-height:1.55; margin:0; }}
        .family-steps {{ display:grid; gap:10px; }}
        .family-steps div {{ display:grid; grid-template-columns:42px 1fr; gap:12px; align-items:center; background:#f4efe5; border:1px solid #e3d8c7; border-radius:16px; padding:12px; }}
        .family-steps b {{ width:34px; height:34px; border-radius:50%; display:grid; place-items:center; background:{GREEN}; color:#fff; }}
        .family-steps span {{ color:{INK}; font-weight:760; }}
        .family-security-strip {{ display:grid; grid-template-columns:1.4fr repeat(4,1fr); gap:0; border:1px solid #e3d8c7; background:#edf4ee; border-radius:22px; overflow:hidden; margin-bottom:16px; }}
        .family-security-strip > div {{ padding:20px; border-right:1px solid #d6ddcf; display:grid; grid-template-columns:42px 1fr; gap:12px; align-items:center; }}
        .family-security-strip > div:last-child {{ border-right:0; }}
        .family-security-strip span {{ width:38px; height:38px; border-radius:50%; background:#fffdf8; display:grid; place-items:center; color:{GREEN}; font-size:1.25rem; }}
        .family-security-strip b {{ display:block; color:{INK}; }}
        .family-security-strip em {{ display:block; color:{MUTED}; font-style:normal; font-size:.82rem; margin-top:3px; }}
        .family-security-strip .security-main b {{ font-family:Georgia,serif; font-size:1.25rem; }}
        .family-live-note {{ background:#fffdf8; border:1px solid #e3d8c7; border-radius:18px; padding:18px; color:{INK}; line-height:1.5; margin-bottom:18px; }}
        .family-message-preview {{ margin-top:12px; }}
        .caregiver-summary-stage {{ display:grid; grid-template-columns:minmax(420px,560px) minmax(310px,1fr); gap:34px; align-items:start; margin:10px 0 20px; }}
        .caregiver-phone-shell {{ display:grid; justify-items:center; }}
        .caregiver-phone {{ position:relative; width:100%; max-width:480px; min-height:980px; background:#fffdf8; border:1px solid #e3d8c7; border-radius:42px; padding:32px 30px 20px; color:{INK}; box-shadow:0 22px 60px rgba(37,65,63,.16), inset 0 0 0 8px rgba(255,255,255,.45); overflow:hidden; }}
        .caregiver-phone:before {{ content:""; position:absolute; inset:0; background:radial-gradient(circle at 84% 7%, rgba(127,169,140,.17), transparent 24%), radial-gradient(circle at 14% 18%, rgba(230,215,191,.22), transparent 28%); pointer-events:none; }}
        .caregiver-phone > * {{ position:relative; z-index:1; }}
        .ios-notch {{ position:absolute; top:10px; left:50%; transform:translateX(-50%); width:126px; height:30px; border-radius:999px; background:#111827; z-index:2; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }}
        .ios-status {{ display:flex; justify-content:space-between; align-items:center; margin:4px 6px 26px; color:{INK}; font-size:.93rem; }}
        .ios-status b {{ font-size:1.05rem; }}
        .ios-status span {{ color:#111827; font-size:.78rem; letter-spacing:.04em; }}
        .summary-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }}
        .summary-brand {{ display:flex; align-items:center; gap:10px; color:{GREEN}; font-size:1.75rem; font-weight:950; }}
        .summary-brand span {{ width:36px; height:36px; border:2px solid {GREEN}; border-radius:11px; display:grid; place-items:center; background:#edf4ee; font-size:1.05rem; }}
        .summary-header-actions {{ display:flex; align-items:center; gap:12px; }}
        .summary-bell, .summary-avatar {{ position:relative; width:44px; height:44px; border-radius:50%; display:grid; place-items:center; background:#fff; border:1px solid #eadfcd; color:{INK} !important; text-decoration:none !important; box-shadow:0 4px 14px rgba(37,65,63,.07); font-weight:950; }}
        .summary-bell em {{ position:absolute; top:1px; right:0; min-width:18px; height:18px; padding:0 4px; border-radius:999px; display:grid; place-items:center; background:#ef4444; color:white; font-style:normal; font-size:.65rem; }}
        .summary-avatar {{ background:linear-gradient(135deg,#e7c6a1,#7fa98c); color:#fff !important; }}
        .summary-greeting-row {{ display:flex; justify-content:space-between; align-items:flex-end; gap:14px; margin-bottom:18px; }}
        .summary-greeting-row p {{ color:{INK}; font-size:1.2rem; margin:0 0 4px; }}
        .summary-greeting-row h2 {{ color:{INK}; font-size:2.55rem; line-height:1.05; margin:0; font-weight:950; letter-spacing:0; }}
        .summary-greeting-row h2 span {{ color:#b9904b; }}
        .summary-video-btn {{ display:inline-flex; align-items:center; gap:8px; border:1px solid #e3d8c7; background:#fff; color:{INK} !important; text-decoration:none !important; border-radius:18px; padding:12px 15px; font-weight:850; box-shadow:0 6px 18px rgba(37,65,63,.08); white-space:nowrap; }}
        .summary-status-card {{ display:grid; grid-template-columns:70px 1fr 82px; gap:16px; align-items:center; min-height:120px; border-radius:22px; border:1px solid #d4e1d3; background:linear-gradient(135deg,#fbfdf8,#eef6ed); padding:18px; color:{INK} !important; text-decoration:none !important; box-shadow:0 10px 28px rgba(37,65,63,.09); margin-bottom:16px; }}
        .summary-status-card b, .summary-ai-card b, .summary-section-card b, .summary-alert-card b {{ color:{INK}; font-weight:950; }}
        .summary-status-card span, .summary-status-card small {{ display:block; color:{MUTED}; margin-top:4px; }}
        .summary-check {{ width:62px; height:62px; border-radius:50%; display:grid; place-items:center; background:{GREEN}; color:#fff; font-size:2rem; font-weight:950; }}
        .summary-patient-photo {{ width:78px; height:78px; border-radius:50%; display:grid; place-items:center; background:linear-gradient(135deg,#f2e4d4,#edf4ee); border:4px solid #97c09d; color:{GREEN}; font-size:2rem; font-weight:950; }}
        .summary-ai-card, .summary-section-card, .summary-alert-card {{ display:block; border:1px solid #eadfcd; border-radius:22px; background:rgba(255,255,255,.82); padding:18px; color:{INK} !important; text-decoration:none !important; box-shadow:0 8px 24px rgba(37,65,63,.07); margin-bottom:16px; }}
        .summary-ai-card {{ position:relative; min-height:178px; padding-right:148px; overflow:hidden; }}
        .summary-ai-card p {{ color:{INK}; line-height:1.48; margin:18px 0 12px; max-width:250px; }}
        .summary-ai-card small {{ color:{MUTED}; }}
        .summary-bot {{ position:absolute; right:16px; bottom:6px; transform:scale(.9); transform-origin:bottom right; }}
        .summary-card-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }}
        .summary-card-head span, .summary-card-head a {{ color:{GREEN} !important; font-weight:850; font-size:.84rem; text-decoration:none !important; }}
        .summary-metric-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
        .summary-metric-tile {{ position:relative; min-height:170px; border:1px solid #eadfcd; border-radius:18px; padding:14px 12px; background:#fff; color:{INK} !important; text-decoration:none !important; overflow:hidden; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .summary-metric-tile span {{ width:42px; height:42px; border-radius:50%; display:grid; place-items:center; margin-bottom:9px; background:#eaf2ea; color:{GREEN}; font-size:1.25rem; }}
        .summary-metric-tile b {{ display:block; color:{MUTED}; font-size:.78rem; font-weight:850; margin-bottom:7px; }}
        .summary-metric-tile strong {{ display:inline-block; color:{INK}; font-size:1.55rem; line-height:1; font-weight:950; }}
        .summary-metric-tile small {{ color:{INK}; margin-left:3px; font-size:.8rem; }}
        .summary-metric-tile em {{ display:block; color:{GREEN}; font-style:normal; font-size:.8rem; margin:5px 0 8px; }}
        .summary-metric-tile svg {{ color:{GREEN}; position:absolute; left:12px; right:12px; bottom:10px; width:calc(100% - 24px); height:34px; }}
        .summary-metric-tile.sleep span, .summary-metric-tile.sleep svg {{ color:#5d88bd; background:#edf4fb; }}
        .summary-metric-tile.activity span, .summary-metric-tile.activity svg {{ color:#e59a21; background:#fff3dc; }}
        .summary-metric-tile.medication span, .summary-metric-tile.medication svg {{ color:{GREEN}; background:#edf4ee; }}
        .summary-quick-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }}
        .summary-quick-link {{ position:relative; min-height:112px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:9px; border:1px solid #eadfcd; border-radius:18px; background:#fff; color:{INK} !important; text-decoration:none !important; text-align:center; box-shadow:0 5px 16px rgba(37,65,63,.06); transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease; }}
        .summary-quick-link:hover, .summary-video-btn:hover, .summary-status-card:hover, .summary-ai-card:hover, .summary-alert-card:hover {{ transform:translateY(-2px); border-color:{GREEN}; box-shadow:0 12px 26px rgba(37,65,63,.12); }}
        .summary-quick-link span {{ width:44px; height:44px; display:grid; place-items:center; border-radius:16px; background:#f4efe5; font-size:1.4rem; }}
        .summary-quick-link b {{ color:{INK}; font-size:.78rem; line-height:1.18; }}
        .summary-quick-link em {{ position:absolute; top:-9px; right:-7px; min-width:23px; height:23px; border-radius:999px; display:grid; place-items:center; background:#ef4444; color:#fff; font-style:normal; font-size:.76rem; font-weight:950; }}
        .summary-alert-card {{ background:#fff8f6; border-color:#f3cfc7; }}
        .summary-alert-row {{ display:grid; grid-template-columns:48px 1fr auto; align-items:center; gap:12px; }}
        .summary-alert-row > span {{ width:46px; height:46px; border-radius:16px; display:grid; place-items:center; background:#ffe2e2; color:{RED}; font-size:1.5rem; }}
        .summary-alert-row small {{ display:block; color:{MUTED}; margin-top:4px; }}
        .summary-alert-row em {{ color:{RED}; font-style:normal; font-weight:850; white-space:nowrap; }}
        .summary-list-row {{ display:grid; grid-template-columns:44px 1fr; gap:12px; align-items:center; border-top:1px solid #eadfcd; padding:12px 0; }}
        .summary-list-row:first-of-type {{ border-top:0; }}
        .summary-list-row span {{ width:40px; height:40px; border-radius:14px; display:grid; place-items:center; background:#edf4ee; color:{GREEN}; font-size:1.24rem; }}
        .summary-list-row small {{ display:block; color:{MUTED}; margin-top:3px; }}
        .caregiver-live-panel {{ position:sticky; top:20px; border:1px solid #e3d8c7; border-radius:28px; background:linear-gradient(135deg,#fffdf8,#f7f1e6); padding:24px; color:{INK}; box-shadow:0 18px 42px rgba(37,65,63,.1); }}
        .caregiver-live-panel h3 {{ color:{INK}; margin:7px 0 8px; font-size:1.8rem; line-height:1.12; font-weight:950; }}
        .caregiver-live-panel p {{ color:#3e4e4b; line-height:1.55; margin:0 0 16px; }}
        .caregiver-live-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin-bottom:16px; }}
        .caregiver-live-grid a {{ border:1px solid #eadfcd; border-radius:16px; background:#fff; padding:14px; color:{INK} !important; text-decoration:none !important; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .caregiver-live-grid b {{ display:block; font-size:.95rem; margin-bottom:5px; }}
        .caregiver-live-grid span {{ color:{MUTED}; font-size:.82rem; line-height:1.35; }}
        .caregiver-live-card {{ border:1px solid #eadfcd; border-radius:18px; background:#fff; padding:16px; margin-bottom:14px; }}
        .nesto-hero {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
        .nesto-bot {{ position:relative; width:104px; height:132px; flex:0 0 auto; animation:nesto-bob 3.2s ease-in-out infinite; transform-origin:center bottom; }}
        .nesto-head {{ position:absolute; left:20px; top:8px; width:64px; height:52px; border-radius:25px; background:#f7f2e8; border:2px solid #d9d0bd; box-shadow:inset 0 -6px 0 rgba(127,169,140,.14), 0 10px 22px rgba(37,65,63,.12); }}
        .nesto-ear {{ position:absolute; top:24px; width:15px; height:28px; border-radius:999px; background:#8fa98c; border:2px solid #d9d0bd; }}
        .nesto-ear.left {{ left:9px; }}
        .nesto-ear.right {{ right:9px; }}
        .nesto-face {{ position:absolute; left:27px; top:16px; width:50px; height:35px; border-radius:18px; background:#25413f; overflow:hidden; }}
        .nesto-eye {{ position:absolute; top:10px; width:7px; height:10px; border-radius:999px; background:#b8f2d4; animation:nesto-blink 4.8s infinite; }}
        .nesto-eye.left {{ left:13px; }}
        .nesto-eye.right {{ right:13px; }}
        .nesto-smile {{ position:absolute; left:19px; top:20px; width:13px; height:7px; border-bottom:3px solid #b8f2d4; border-radius:0 0 999px 999px; }}
        .nesto-body {{ position:absolute; left:26px; top:62px; width:52px; height:58px; border-radius:22px 22px 18px 18px; background:#f7f2e8; border:2px solid #d9d0bd; box-shadow:inset 0 -7px 0 rgba(127,169,140,.18); }}
        .nesto-heart {{ position:absolute; left:44px; top:78px; width:17px; height:14px; color:#7fa98c; font-size:16px; animation:nesto-glow 2.3s ease-in-out infinite; }}
        .nesto-arm {{ position:absolute; top:69px; width:13px; height:42px; border-radius:999px; background:#d9d0bd; }}
        .nesto-arm.left {{ left:12px; transform:rotate(14deg); }}
        .nesto-arm.right {{ right:11px; transform-origin:top center; animation:nesto-wave 2.8s ease-in-out infinite; }}
        .nesto-base {{ position:absolute; left:23px; bottom:3px; width:58px; height:18px; border-radius:999px; background:#8fa98c; box-shadow:0 8px 15px rgba(37,65,63,.13); }}
        .nesto-shadow {{ width:78px; height:12px; border-radius:999px; background:rgba(37,65,63,.12); position:absolute; left:13px; bottom:-4px; animation:nesto-shadow 3.2s ease-in-out infinite; }}
        .nesto-note {{ display:inline-flex; align-items:center; gap:7px; border-radius:999px; background:#edf4ee; color:#25413f; padding:7px 10px; font-size:.78rem; font-weight:850; border:1px solid #cbdccb; }}
        @keyframes nesto-bob {{ 0%,100% {{ transform:translateY(0) rotate(-1deg); }} 50% {{ transform:translateY(-7px) rotate(1deg); }} }}
        @keyframes nesto-wave {{ 0%,100% {{ transform:rotate(-20deg); }} 45% {{ transform:rotate(-54deg); }} 70% {{ transform:rotate(-30deg); }} }}
        @keyframes nesto-blink {{ 0%,92%,100% {{ transform:scaleY(1); }} 95% {{ transform:scaleY(.12); }} }}
        @keyframes nesto-glow {{ 0%,100% {{ opacity:.75; transform:scale(1); }} 50% {{ opacity:1; transform:scale(1.16); }} }}
        @keyframes nesto-shadow {{ 0%,100% {{ transform:scaleX(1); opacity:.12; }} 50% {{ transform:scaleX(.82); opacity:.08; }} }}

        .admin-shell {{ background:#fff; border:1px solid #e9e7f5; border-radius:24px; overflow:hidden; box-shadow:0 18px 46px rgba(30,31,48,.13); display:grid; grid-template-columns:170px 1fr; }}
        .admin-side {{ background:#101d32; padding:18px 14px; color:#fff; }}
        .admin-nav {{ display:flex; flex-direction:column; gap:8px; margin-top:20px; }}
        .admin-nav span {{ padding:10px 12px; border-radius:12px; color:#cbd5e1; font-size:.84rem; font-weight:750; }}
        .admin-nav .active {{ background:{CORAL}; color:#fff; }}
        .admin-main {{ background:#f8fafc; padding:20px; }}
        .admin-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:12px; }}
        .admin-two {{ display:grid; grid-template-columns:1.15fr 1fr; gap:12px; }}
        .admin-card {{ background:#fff; border:1px solid #dddfe2; border-radius:14px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.06); }}
        .admin-kpi {{ color:{INK}; font-size:1.55rem; font-weight:950; margin-top:4px; }}

        .provider-shell {{ display:grid; grid-template-columns:248px 1fr; background:#fffdf8; border:1px solid #e3d8c7; border-radius:26px; overflow:hidden; box-shadow:0 22px 60px rgba(37,65,63,.12); margin-bottom:18px; }}
        .provider-navrail {{ background:linear-gradient(180deg,#fbf8f0,#efe7d8); border-right:1px solid #e3d8c7; padding:20px 14px; min-height:1040px; color:{INK}; }}
        .provider-brand {{ display:flex; align-items:center; gap:10px; margin-bottom:22px; }}
        .provider-brand span, .provider-user span {{ display:block; color:{MUTED}; font-size:.78rem; margin-top:2px; }}
        .provider-logo {{ width:36px; height:36px; border:2px solid {GREEN}; border-radius:10px; display:grid; place-items:center; color:{GREEN}; font-weight:950; text-decoration:none !important; background:rgba(255,255,255,.7); transition:transform .16s ease, box-shadow .16s ease; }}
        .provider-logo:hover {{ transform:translateY(-2px); box-shadow:0 8px 16px rgba(37,65,63,.12); }}
        .provider-nav-label {{ color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; font-size:.68rem; font-weight:950; margin:18px 10px 8px; }}
        .provider-navitem {{ display:flex; align-items:center; gap:10px; min-height:38px; padding:9px 10px; border-radius:10px; color:{INK} !important; font-weight:760; font-size:.84rem; margin-bottom:4px; text-decoration:none !important; cursor:pointer; transition:background .16s ease, transform .16s ease, box-shadow .16s ease; }}
        .provider-navitem:hover {{ background:rgba(255,255,255,.72); transform:translateX(2px); box-shadow:0 6px 14px rgba(37,65,63,.08); }}
        .provider-navitem.active {{ background:#e6dfcf; box-shadow:inset 4px 0 0 {GREEN}; }}
        .provider-navitem b {{ margin-left:auto; background:#d9534f; color:#fff; border-radius:999px; min-width:20px; height:20px; display:grid; place-items:center; font-size:.68rem; }}
        .provider-user {{ display:flex; align-items:center; gap:10px; margin-top:90px; padding:12px; background:rgba(255,255,255,.62); border:1px solid #e3d8c7; border-radius:14px; }}
        .provider-nesto-promo {{ margin-top:24px; border:1px solid #e3d8c7; border-radius:18px; background:rgba(255,255,255,.72); padding:16px 14px; text-align:center; box-shadow:0 10px 24px rgba(37,65,63,.08); }}
        .provider-nesto-promo .nesto-bot {{ transform:scale(.86); margin:10px auto 18px; }}
        .provider-nesto-promo b {{ display:block; color:{INK}; font-size:1.08rem; }}
        .provider-nesto-promo span {{ display:block; color:{MUTED}; font-size:.78rem; margin:4px 0 12px; }}
        .provider-nesto-promo a {{ display:block; border-radius:10px; background:{GREEN}; color:#fff !important; text-decoration:none !important; font-weight:850; padding:10px 12px; }}
        .small-avatar {{ width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,{GREEN},{CORAL}); color:#fff; display:inline-grid; place-items:center; font-style:normal; font-weight:950; margin-right:8px; flex:0 0 auto; }}
        .provider-main {{ padding:22px; background:linear-gradient(135deg,#fffdf8,#f7f1e7); }}
        .provider-topbar {{ display:grid; grid-template-columns:1fr auto auto; align-items:center; gap:12px; margin-bottom:18px; }}
        .provider-search {{ min-height:42px; border:1px solid #e3d8c7; border-radius:12px; background:#fff; color:{MUTED}; display:flex; align-items:center; padding:0 14px; font-weight:760; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .provider-bell {{ position:relative; width:42px; height:42px; border:1px solid #e3d8c7; border-radius:12px; background:#fff; display:grid; place-items:center; text-decoration:none !important; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .provider-bell b {{ position:absolute; top:-7px; right:-7px; min-width:18px; height:18px; padding:0 4px; border-radius:999px; background:{RED}; color:#fff; display:grid; place-items:center; font-size:.62rem; }}
        .provider-profile {{ min-height:42px; border:1px solid #e3d8c7; border-radius:14px; background:#fff; display:flex; align-items:center; gap:8px; padding:7px 10px; color:{INK} !important; text-decoration:none !important; box-shadow:0 4px 14px rgba(37,65,63,.05); }}
        .provider-profile span span, .provider-profile em {{ display:block; color:{MUTED}; font-size:.72rem; font-style:normal; font-weight:700; }}
        .provider-profile i {{ color:{MUTED}; font-style:normal; }}
        .provider-main-top {{ display:flex; justify-content:space-between; gap:14px; align-items:center; margin-bottom:18px; }}
        .provider-main-top h3 {{ color:{INK}; margin:0 0 4px 0; font-size:1.4rem; font-weight:950; }}
        .provider-main-top p {{ margin:0; color:{MUTED}; font-size:.9rem; }}
        .date-pill {{ background:#fff; border:1px solid #e3d8c7; border-radius:12px; padding:10px 14px; color:{INK}; font-weight:800; box-shadow:0 4px 14px rgba(37,65,63,.06); white-space:nowrap; }}
        .provider-hero-card {{ display:grid; grid-template-columns:1fr 160px; align-items:center; gap:20px; border:1px solid #cbdccb; border-radius:26px; padding:24px; margin-bottom:18px; background:radial-gradient(circle at 88% 20%, rgba(127,169,140,.28), transparent 30%), linear-gradient(135deg,#fff8ec,#edf4ee); box-shadow:0 18px 44px rgba(37,65,63,.12); color:{INK}; }}
        .provider-hero-card h3 {{ color:{INK}; font-size:1.75rem; line-height:1.12; margin:6px 0 8px; font-weight:950; }}
        .provider-hero-card p {{ color:#3e4e4b; line-height:1.5; max-width:760px; margin:0 0 14px; }}
        .provider-hero-metrics {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; }}
        .provider-hero-metrics span {{ border:1px solid #d8cdbb; background:rgba(255,255,255,.7); border-radius:14px; padding:10px 12px; color:{MUTED}; font-weight:760; }}
        .provider-hero-metrics b {{ display:block; color:{INK}; font-size:1.08rem; font-weight:950; margin-bottom:2px; }}
        .provider-hero-robot {{ display:grid; justify-items:center; gap:8px; }}
        .provider-hero-robot .nesto-bot {{ transform:scale(1.06); }}
        .provider-nesto-card {{ display:grid; grid-template-columns:1fr auto; align-items:center; gap:18px; background:radial-gradient(circle at 88% 28%, rgba(127,169,140,.2), transparent 30%), linear-gradient(135deg,#fff,#f1eadf); border:1px solid #e3d8c7; border-radius:20px; padding:18px; margin-bottom:12px; box-shadow:0 8px 24px rgba(37,65,63,.08); }}
        .provider-nesto-copy h3 {{ color:{INK}; font-size:1.22rem; margin:4px 0 6px; font-weight:950; }}
        .provider-nesto-copy p {{ color:{MUTED}; line-height:1.45; margin:0 0 12px; }}
        .provider-nesto-stats {{ display:grid; grid-template-columns:repeat(4,minmax(92px,1fr)); gap:10px; }}
        .provider-nesto-stats div {{ background:rgba(255,255,255,.75); border:1px solid #eadfcd; border-radius:14px; padding:10px; }}
        .provider-nesto-stats b {{ display:block; color:{INK}; font-size:1rem; font-weight:950; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
        .provider-nesto-stats span {{ display:block; color:{MUTED}; font-size:.72rem; font-weight:850; margin-top:3px; }}
        .provider-nesto-robot {{ min-width:130px; display:grid; justify-items:center; gap:8px; }}
        .provider-nesto-robot .nesto-bot {{ transform:scale(.92); }}
        .provider-kpis {{ display:grid; grid-template-columns:repeat(4,minmax(130px,1fr)); gap:12px; margin-bottom:12px; }}
        .provider-kpi {{ background:#fff; border:1px solid #e3d8c7; border-radius:14px; padding:16px; min-height:116px; box-shadow:0 4px 16px rgba(37,65,63,.06); display:grid; grid-template-columns:48px 1fr; column-gap:12px; align-items:start; }}
        .provider-kpi i {{ width:48px; height:48px; border-radius:16px; background:#edf4ee; color:{GREEN}; display:grid; place-items:center; font-style:normal; font-size:1.25rem; grid-row:1 / span 3; }}
        .provider-kpi:nth-child(2) i {{ background:#eef5fb; color:{BLUE}; }}
        .provider-kpi:nth-child(3) i {{ background:#fff3dc; color:{AMBER}; }}
        .provider-kpi:nth-child(4) i {{ background:#e6f2e9; color:{GREEN}; }}
        .provider-kpi span {{ color:{MUTED}; font-size:.78rem; font-weight:850; }}
        .provider-kpi strong {{ display:block; color:{INK}; font-size:1.6rem; margin:8px 0 5px; }}
        .provider-kpi em {{ font-style:normal; font-size:.75rem; font-weight:900; margin-right:6px; }}
        .provider-kpi em.positive {{ color:#3f8d55; }}
        .provider-kpi em.negative {{ color:#d9534f; }}
        .provider-kpi small {{ color:{MUTED}; font-size:.68rem; }}
        .provider-overview-layout {{ display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:14px; align-items:start; }}
        .provider-overview-main {{ display:grid; gap:12px; min-width:0; }}
        .provider-side-stack {{ display:grid; gap:12px; align-content:start; min-width:0; }}
        .provider-grid {{ display:grid; gap:12px; margin-bottom:12px; }}
        .provider-overview-main .provider-grid {{ margin-bottom:0; }}
        .provider-grid.two {{ grid-template-columns:1.15fr 1fr; }}
        .provider-grid.three {{ grid-template-columns:1fr 1fr 1fr; }}
        .provider-card {{ background:#fff; border:1px solid #e3d8c7; border-radius:16px; padding:16px; box-shadow:0 4px 16px rgba(37,65,63,.06); }}
        .panel-head {{ display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px; color:{INK}; }}
        .panel-head b {{ font-weight:950; }}
        .panel-head span, .panel-head a {{ color:{GREEN} !important; font-size:.78rem; font-weight:850; text-decoration:none !important; }}
        .provider-row {{ display:flex; align-items:center; gap:10px; min-height:54px; border-bottom:1px solid #ede4d8; padding:10px 0; color:{INK}; }}
        .provider-row:last-child {{ border-bottom:0; }}
        .provider-row b {{ display:block; color:{INK}; font-size:.9rem; }}
        .provider-row span {{ display:block; color:{MUTED}; font-size:.76rem; margin-top:2px; }}
        .provider-row time {{ color:{MUTED}; font-size:.75rem; min-width:54px; }}
        .provider-icon {{ width:34px; height:34px; border-radius:50%; display:grid; place-items:center; font-weight:950; font-size:.75rem; flex:0 0 auto; }}
        .provider-icon.red {{ background:#ffe7e3; color:#d9534f; }}
        .provider-icon.amber {{ background:#fff2d7; color:#d89100; }}
        .provider-icon.green {{ background:#e6f2e9; color:{GREEN}; }}
        .donut-panel {{ display:flex; align-items:center; gap:22px; min-height:190px; }}
        .donut-panel.compact {{ min-height:130px; gap:14px; }}
        .donut-panel.right-rail {{ flex-direction:column; align-items:flex-start; }}
        .provider-donut {{ width:156px; height:156px; border-radius:50%; display:grid; place-items:center; flex:0 0 auto; }}
        .donut-panel.compact .provider-donut {{ width:116px; height:116px; }}
        .provider-donut div {{ width:96px; height:96px; border-radius:50%; background:#fffdf8; display:grid; place-items:center; text-align:center; color:{INK}; box-shadow:inset 0 0 0 1px #e3d8c7; }}
        .donut-panel.compact .provider-donut div {{ width:72px; height:72px; }}
        .provider-donut strong {{ display:block; font-size:1.65rem; line-height:1; }}
        .provider-donut span {{ display:block; color:{MUTED}; font-size:.72rem; margin-top:-18px; }}
        .legend {{ display:grid; gap:12px; width:100%; }}
        .legend div {{ display:grid; grid-template-columns:12px 1fr auto; align-items:center; gap:8px; color:{INK}; }}
        .legend span {{ width:10px; height:10px; border-radius:50%; }}
        .legend b {{ font-size:.82rem; }}
        .legend em {{ font-style:normal; color:{MUTED}; font-size:.78rem; }}
        .provider-table {{ display:grid; grid-template-columns:1.4fr .8fr .9fr .7fr; align-items:center; gap:8px; padding:8px 0; border-bottom:1px solid #ede4d8; color:{INK}; }}
        .provider-table.patients {{ grid-template-columns:1.25fr .45fr 1fr .75fr .85fr .65fr; }}
        .provider-table:last-child {{ border-bottom:0; }}
        .provider-table span {{ font-size:.78rem; color:{INK}; }}
        .provider-table-head span {{ color:{MUTED}; font-weight:850; font-size:.72rem; }}
        .workbar {{ width:112px; height:7px; background:#efe8dc; border-radius:999px; overflow:hidden; margin-left:auto; }}
        .workbar span {{ display:block; height:100%; background:{GREEN}; border-radius:999px; }}
        .provider-row.workload time {{ min-width:44px; text-align:right; font-weight:850; color:{INK}; }}
        .provider-risk-chart {{ min-height:230px; display:grid; grid-template-columns:160px 1fr; grid-template-rows:1fr auto; gap:8px 14px; align-items:end; }}
        .risk-legend {{ grid-row:1 / span 2; align-self:center; display:grid; gap:12px; color:{INK}; }}
        .risk-legend span {{ display:grid; grid-template-columns:10px 1fr auto; align-items:center; gap:8px; font-size:.8rem; color:{INK}; }}
        .risk-legend i {{ width:9px; height:9px; border-radius:50%; display:block; }}
        .risk-legend b {{ font-weight:950; color:{MUTED}; }}
        .risk-bars {{ grid-column:2; height:44px; display:grid; grid-template-columns:repeat(7,1fr); align-items:end; gap:12px; }}
        .risk-bars span {{ display:block; border-radius:999px 999px 4px 4px; min-height:14px; opacity:.86; }}
        .risk-bars.high span {{ background:#e8584f; }}
        .risk-bars.medium span {{ background:#efa629; }}
        .risk-bars.low span {{ background:#5e9b6c; }}
        .risk-days {{ grid-column:2; display:grid; grid-template-columns:repeat(7,1fr); gap:8px; color:{MUTED}; font-size:.68rem; text-align:center; }}
        .provider-value-strip {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; background:#fffdf8; border:1px solid #e3d8c7; border-radius:18px; padding:16px; margin-bottom:18px; color:{INK}; box-shadow:0 8px 24px rgba(37,65,63,.08); }}
        .provider-value-strip span {{ text-align:center; font-weight:760; font-size:.86rem; }}
        .robot-station-hero {{ display:grid; grid-template-columns:1.05fr .95fr; gap:22px; align-items:center; border:1px solid #cbdccb; border-radius:30px; padding:28px; margin-bottom:16px; background:radial-gradient(circle at 82% 22%, rgba(127,169,140,.28), transparent 30%), linear-gradient(135deg,#fff8ec,#edf4ee 58%,#f8efe5); box-shadow:0 22px 54px rgba(37,65,63,.14); color:{INK}; }}
        .robot-station-identity h3 {{ color:{INK}; font-size:2.05rem; line-height:1.08; margin:8px 0 10px; font-weight:950; }}
        .robot-station-identity p {{ color:#3e4e4b; font-size:1rem; line-height:1.55; max-width:650px; margin:0 0 16px; }}
        .robot-progress-wrap {{ border:1px solid #d8cdbb; background:rgba(255,255,255,.72); border-radius:18px; padding:14px; margin-bottom:12px; }}
        .robot-progress-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px; color:{INK}; }}
        .robot-progress-head b {{ font-size:1.2rem; }}
        .robot-progress {{ height:14px; border-radius:999px; background:#e1e5e1; overflow:hidden; }}
        .robot-progress span {{ display:block; height:100%; border-radius:999px; background:linear-gradient(90deg,{GREEN},{CORAL}); }}
        .robot-station-stats {{ display:grid; grid-template-columns:repeat(2,minmax(150px,1fr)); gap:10px; }}
        .robot-station-stats span {{ display:block; border:1px solid #e3d8c7; background:rgba(255,255,255,.7); border-radius:16px; padding:12px; color:{MUTED}; font-weight:760; line-height:1.35; }}
        .robot-station-stats b {{ display:block; color:{INK}; font-size:1.08rem; font-weight:950; margin-bottom:2px; }}
        .robot-station-visual {{ display:grid; place-items:center; min-height:300px; }}
        .robot-stage {{ position:relative; display:grid; place-items:center; width:min(360px,100%); min-height:280px; border:1px solid #e3d8c7; border-radius:28px; background:linear-gradient(180deg,rgba(255,255,255,.82),rgba(255,248,236,.64)); box-shadow:inset 0 0 0 10px rgba(255,255,255,.36), 0 18px 40px rgba(37,65,63,.1); }}
        .robot-stage .nesto-bot {{ transform:scale(1.58); margin-top:28px; }}
        .robot-speech {{ position:absolute; right:18px; top:18px; max-width:190px; background:#ffffff; border:1px solid #e3d8c7; border-radius:18px; padding:12px 14px; color:{INK}; font-weight:850; line-height:1.35; box-shadow:0 10px 24px rgba(37,65,63,.1); }}
        .robot-status-grid {{ display:grid; grid-template-columns:repeat(4,minmax(160px,1fr)); gap:14px; margin-bottom:16px; }}
        .robot-status-card {{ border:1px solid #e3d8c7; border-radius:20px; padding:18px; background:#ffffff; min-height:156px; box-shadow:0 8px 22px rgba(37,65,63,.07); color:{INK}; }}
        .robot-status-icon {{ width:52px; height:52px; border-radius:18px; display:grid; place-items:center; background:#edf4ee; color:{GREEN}; font-size:1.45rem; margin-bottom:14px; }}
        .robot-status-card span {{ display:block; color:{MUTED}; font-size:.78rem; font-weight:900; text-transform:uppercase; letter-spacing:.05em; }}
        .robot-status-card b {{ display:block; color:{INK}; font-size:1.55rem; line-height:1.12; margin:8px 0 6px; font-weight:950; }}
        .robot-status-card em {{ display:block; color:{MUTED}; font-style:normal; line-height:1.35; }}
        .robot-status-card.room .robot-status-icon {{ background:#f3eef7; }}
        .robot-status-card.movement .robot-status-icon {{ background:#fff3dc; color:{AMBER}; }}
        .robot-status-card.alerts .robot-status-icon {{ background:#ffe2e2; color:{RED}; }}
        .provider-active-preview {{ display:grid; grid-template-columns:58px 1fr; gap:14px; align-items:center; border:1px solid #cbdccb; background:#edf4ee; border-radius:16px; padding:14px; margin-bottom:12px; color:{INK}; }}
        .provider-active-preview h4 {{ color:{INK}; margin:2px 0 5px; font-size:1.08rem; font-weight:950; }}
        .provider-active-preview p {{ color:#4f7364; margin:0 0 6px; line-height:1.4; }}
        .provider-active-preview b {{ color:#25413f; font-weight:900; line-height:1.4; }}
        .provider-focus-panel {{ display:grid; grid-template-columns:68px 1fr; gap:16px; align-items:center; background:#ffffff; border:1px solid #d8cdbb; border-radius:20px; padding:18px; margin:4px 0 14px; box-shadow:0 10px 30px rgba(37,65,63,.08); color:{INK}; }}
        .provider-focus-icon {{ width:58px; height:58px; border-radius:18px; display:grid; place-items:center; background:#edf4ee; color:{GREEN}; font-size:1.55rem; border:1px solid #cbdccb; }}
        .provider-focus-panel h3 {{ color:{INK}; margin:2px 0 6px; font-size:1.25rem; font-weight:950; }}
        .provider-focus-panel p {{ color:{MUTED}; margin:0 0 8px; line-height:1.45; }}
        .provider-focus-panel b {{ color:#31534b; font-weight:850; line-height:1.45; }}

        .role-strip {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }}
        .role-chip {{ border:1px solid {border}; background:{panel}; border-radius:999px; padding:9px 13px; color:{text}; font-weight:850; box-shadow:0 8px 20px rgba(15,23,42,.05); }}
        .role-grid {{ display:grid; grid-template-columns:repeat(3,minmax(190px,1fr)); gap:14px; margin-bottom:14px; }}
        .role-card {{ background:{panel}; border:1px solid {border}; border-radius:14px; padding:18px; box-shadow:0 1px 2px rgba(0,0,0,.08); min-height:150px; }}
        .role-icon {{ width:48px; height:48px; border-radius:18px; display:flex; align-items:center; justify-content:center; background:#e9f2ec; color:{INK}; font-size:1.35rem; margin-bottom:12px; }}
        .role-title {{ color:{text}; font-size:1.03rem; font-weight:950; margin-bottom:6px; }}
        .role-copy {{ color:{muted}; font-size:.9rem; line-height:1.45; }}
        .outcome-grid {{ display:grid; grid-template-columns:repeat(3,minmax(190px,1fr)); gap:14px; }}
        .outcome-card {{ background:#ffffff; border:1px solid {border}; border-radius:14px; padding:18px; box-shadow:0 1px 2px rgba(0,0,0,.08); }}
        .outcome-icon {{ font-size:1.45rem; margin-bottom:8px; }}
        .data-note {{ background:#edf4ee; border:1px solid #cbdccb; border-radius:14px; padding:16px 18px; margin-bottom:16px; color:#25413f; }}
        .notice-pop {{ border:1px solid #cbdccb; background:#ffffff; color:#25413f; border-radius:14px; padding:16px 18px; margin:0 0 18px 0; box-shadow:0 6px 18px rgba(111,167,166,.16); font-weight:850; }}
        .notice-pop .notice-sub {{ display:block; color:#4f7364; font-size:.9rem; font-weight:650; margin-top:4px; }}

        .welcome-hero {{ position:relative; overflow:hidden; border:1px solid #e3d8c7; border-radius:34px; padding:34px 42px 42px; margin-bottom:18px; background:radial-gradient(circle at 76% 20%, rgba(127,169,140,.22), transparent 26%), linear-gradient(135deg,#fff8ec 0%,#f4efe5 48%,#f8e9df 100%); box-shadow:0 24px 60px rgba(37,65,63,.13); }}
        .welcome-nav {{ display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:34px; }}
        .welcome-brand {{ display:flex; align-items:center; gap:12px; color:{INK}; font-size:1.35rem; font-weight:950; }}
        .welcome-logo {{ width:42px; height:42px; display:grid; place-items:center; border-radius:14px; color:{GREEN}; border:2px solid {GREEN}; background:rgba(255,255,255,.65); }}
        .welcome-links {{ display:flex; align-items:center; gap:22px; color:{MUTED}; font-weight:760; }}
        .welcome-links b {{ background:#ffffff; border:1px solid #e3d8c7; border-radius:999px; padding:10px 16px; color:{INK}; box-shadow:0 10px 22px rgba(37,65,63,.08); }}
        .welcome-grid {{ display:grid; grid-template-columns:1.08fr .92fr; gap:34px; align-items:center; }}
        .welcome-title {{ color:{INK}; font-size:4.3rem; line-height:.98; font-weight:950; letter-spacing:0; max-width:620px; margin:8px 0 18px; }}
        .welcome-copy {{ color:#3e4e4b; font-size:1.18rem; line-height:1.55; max-width:600px; margin:0; }}
        .welcome-actions {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:26px; }}
        .welcome-actions span {{ display:inline-flex; min-height:42px; align-items:center; border-radius:16px; border:1px solid #d8cdbb; background:rgba(255,255,255,.58); padding:10px 16px; color:{INK}; font-weight:900; }}
        .welcome-robot-panel {{ position:relative; min-height:300px; display:grid; grid-template-columns:1fr 150px; align-items:center; gap:12px; padding:20px; border-radius:28px; background:rgba(255,255,255,.38); border:1px solid rgba(227,216,199,.8); }}
        .welcome-robot-panel .nesto-bot {{ transform:scale(1.28); justify-self:center; }}
        .welcome-robot-panel .speech-bubble {{ font-size:1.05rem; }}
        .welcome-note {{ position:absolute; right:18px; bottom:16px; background:#edf4ee; color:{INK}; border:1px solid #cbdccb; border-radius:999px; padding:8px 13px; font-size:.78rem; font-weight:900; }}
        .setup-strip {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }}
        .setup-strip div {{ border:1px solid #e3d8c7; background:#fffdf8; border-radius:18px; padding:16px; box-shadow:0 6px 18px rgba(37,65,63,.06); }}
        .setup-strip b {{ display:block; color:{INK}; font-size:1rem; margin-bottom:5px; }}
        .setup-strip span {{ display:block; color:{MUTED}; font-size:.82rem; line-height:1.35; }}
        .goal-panel {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; border:1px solid #cbdccb; border-radius:20px; background:linear-gradient(135deg,#edf4ee,#fffdf8); padding:20px; margin:12px 0 18px; box-shadow:0 10px 24px rgba(37,65,63,.08); }}
        .goal-label {{ display:inline-block; color:{GREEN}; font-size:.72rem; font-weight:950; text-transform:uppercase; letter-spacing:.1em; margin-bottom:6px; }}
        .goal-panel h3 {{ color:{INK}; font-size:1.45rem; margin:0 0 8px; }}
        .goal-panel p {{ color:#3e4e4b; line-height:1.5; margin:0; font-weight:650; }}
        .consent-card {{ background:#fffdf8; border:1px solid #e3d8c7; border-radius:22px; padding:22px; margin-bottom:18px; box-shadow:0 8px 24px rgba(37,65,63,.08); }}
        .consent-row {{ display:flex; justify-content:space-between; align-items:center; gap:16px; border-top:1px solid #e6ddd0; padding:16px 0 10px; margin-top:10px; }}
        .consent-row b {{ display:block; color:{INK}; font-size:1.06rem; margin-bottom:5px; }}
        .consent-row span {{ display:block; color:{MUTED}; line-height:1.42; }}
        .consent-row em {{ flex:0 0 auto; font-style:normal; border-radius:999px; padding:7px 12px; font-size:.76rem; font-weight:950; }}
        .consent-row em.locked {{ background:#fff3dc; color:{AMBER}; }}
        .consent-row em.opened {{ background:#e9f2ec; color:{GREEN}; }}

        .fb-feed {{ display:grid; gap:14px; margin-bottom:16px; }}
        .fb-post {{ background:{panel}; border:1px solid {border}; border-radius:14px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,.08); }}
        .fb-post-head {{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }}
        .fb-avatar {{ width:42px; height:42px; border-radius:50%; background:#e9f2ec; color:{INK}; display:flex; align-items:center; justify-content:center; font-weight:950; }}
        .fb-post-title {{ color:{text}; font-weight:950; }}
        .fb-actions {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; border-top:1px solid {border}; margin-top:12px; padding-top:10px; color:{BLUE}; font-weight:850; text-align:center; }}

        .chat-workflow {{ display:grid; grid-template-columns:.85fr 1.15fr; gap:16px; align-items:stretch; border:1px solid #cbdccb; border-radius:26px; padding:20px; margin-bottom:14px; background:linear-gradient(135deg,#fffdf8,#edf4ee); box-shadow:0 14px 36px rgba(37,65,63,.1); color:{INK}; }}
        .chat-workflow-copy {{ border:1px solid #d8cdbb; border-radius:20px; padding:20px; background:rgba(255,255,255,.68); }}
        .chat-workflow-copy h3 {{ color:{INK}; font-size:1.45rem; line-height:1.16; margin:6px 0 10px; font-weight:950; }}
        .chat-workflow-copy p {{ color:#3e4e4b; line-height:1.5; margin:0 0 14px; }}
        .chat-steps {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; }}
        .chat-steps span {{ background:#ffffff; border:1px solid #e3d8c7; border-radius:14px; padding:10px; color:{INK}; font-weight:850; }}
        .chat-steps b {{ display:inline-grid; place-items:center; width:22px; height:22px; margin-right:7px; border-radius:50%; background:#e9f2ec; color:{GREEN}; }}
        .admin-action-grid {{ display:grid; grid-template-columns:repeat(2,minmax(170px,1fr)); gap:12px; }}
        .admin-action-card {{ min-height:138px; border:1px solid #e3d8c7; border-radius:20px; background:#ffffff; padding:16px; box-shadow:0 6px 18px rgba(37,65,63,.08); color:{INK}; }}
        .admin-action-card b {{ display:block; color:{INK}; font-size:1.05rem; font-weight:950; margin:9px 0 5px; }}
        .admin-action-card span {{ display:block; color:{MUTED}; font-size:.86rem; line-height:1.38; }}
        .admin-action-icon {{ width:54px; height:54px; border-radius:18px; display:grid; place-items:center; font-size:1.55rem; background:#e9f2ec; }}
        .admin-action-card.purple .admin-action-icon {{ background:#f3eef7; }}
        .admin-action-card.green .admin-action-icon {{ background:#e9f2ec; }}
        .admin-action-card.amber .admin-action-icon {{ background:#fff3dc; }}
        .admin-action-card.red .admin-action-icon {{ background:#ffe2e2; }}
        .decision-command-panel {{ display:grid; grid-template-columns:1.05fr .95fr; gap:16px; border:1px solid #d8cdbb; border-radius:24px; background:#ffffff; padding:20px; margin:18px 0; box-shadow:0 12px 30px rgba(37,65,63,.08); color:{INK}; }}
        .decision-main h3 {{ color:{INK}; font-size:1.55rem; line-height:1.15; margin:6px 0 8px; font-weight:950; }}
        .decision-main p {{ color:{MUTED}; line-height:1.5; margin:0 0 14px; }}
        .decision-request {{ border:1px solid #e3d8c7; background:#fffdf8; border-radius:16px; padding:14px; }}
        .decision-request b {{ display:block; color:{INK}; margin-bottom:5px; }}
        .decision-request span {{ display:block; color:{MUTED}; line-height:1.45; }}
        .decision-next {{ display:grid; gap:10px; }}
        .decision-step {{ display:flex; align-items:center; gap:12px; border:1px solid #e3d8c7; border-radius:16px; padding:12px; background:#f8f5ee; }}
        .decision-step > span {{ width:42px; height:42px; border-radius:14px; display:grid; place-items:center; background:#e9f2ec; color:{GREEN}; font-weight:950; flex:0 0 auto; }}
        .decision-step b {{ display:block; color:{INK}; font-weight:950; }}
        .decision-step em {{ display:block; color:{MUTED}; font-style:normal; margin-top:2px; }}
        .scenario-row {{ display:flex; align-items:center; gap:12px; padding:12px; border-bottom:1px solid {border}; border-radius:14px; }}
        .scenario-row:last-child {{ border-bottom:0; }}
        .scenario-row.active {{ background:#edf4ee; border:1px solid #cbdccb; box-shadow:0 0 0 4px rgba(127,169,140,.12); margin:6px 0; }}
        .empty-action-log {{ border:1px dashed #cbdccb; background:#fffdf8; color:{MUTED}; border-radius:16px; padding:18px; line-height:1.5; font-weight:760; }}
        .chat-shell {{ background:#f4efe5; border:1px solid #e3d8c7; border-radius:18px; padding:18px; max-width:780px; margin:0 auto 18px auto; box-shadow:0 1px 2px rgba(0,0,0,.08); }}
        .chat-top {{ display:flex; align-items:center; gap:12px; padding:10px 12px 16px 12px; border-bottom:1px solid #e2e8f0; }}
        .chat-avatar {{ width:44px; height:44px; border-radius:50%; background:linear-gradient(135deg,{PEACH},{PURPLE}); color:white; display:flex; align-items:center; justify-content:center; font-weight:950; }}
        .bubble-row {{ display:flex; margin:14px 0; width:100%; }}
        .bubble-row.right {{ justify-content:flex-end; }}
        .bubble-pack {{ display:flex; flex-direction:column; max-width:72%; min-width:190px; }}
        .bubble-row.right .bubble-pack {{ align-items:flex-end; }}
        .bubble {{ display:inline-block; width:fit-content; max-width:100%; min-width:120px; white-space:normal; overflow-wrap:break-word; word-break:normal; border-radius:20px; padding:13px 15px; line-height:1.45; font-weight:650; box-shadow:0 6px 18px rgba(15,23,42,.05); }}
        .bubble-row.left .bubble {{ background:white; color:{INK}; border-top-left-radius:6px; }}
        .bubble-row.right .bubble {{ background:{CORAL}; color:white; border-top-right-radius:6px; }}
        .chat-meta {{ color:{MUTED}; font-size:.72rem; margin-top:5px; }}

        .watch-grid {{ display:grid; grid-template-columns:1.05fr 1.4fr; gap:16px; align-items:start; }}
        .watch-face {{ background:#111827; color:#fff; border-radius:34px; padding:24px; min-height:390px; box-shadow:0 20px 48px rgba(17,24,39,.22); }}
        .ring-wrap {{ display:flex; justify-content:center; margin:18px 0; }}
        .ring {{ width:172px; height:172px; border-radius:50%; display:grid; place-items:center; background:conic-gradient({GREEN} 0 78%, #334155 78% 100%); }}
        .ring-inner {{ width:126px; height:126px; border-radius:50%; background:#111827; display:grid; place-items:center; text-align:center; }}
        .ring-score {{ font-size:2.4rem; font-weight:950; color:white; line-height:1; }}
        .watch-list {{ display:grid; gap:10px; }}
        .watch-item {{ display:flex; justify-content:space-between; align-items:center; background:#1f2937; border:1px solid #374151; border-radius:16px; padding:12px; }}
        .wellness-grid {{ display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)); gap:14px; }}
        .wellness-card {{ background:{panel}; border:1px solid {border}; border-radius:20px; padding:18px; min-height:150px; box-shadow:0 8px 24px rgba(15,23,42,.06); }}
        .mini-bars {{ display:flex; align-items:flex-end; gap:8px; height:70px; margin-top:16px; }}
        .mini-bars span {{ display:block; width:100%; border-radius:999px 999px 4px 4px; background:linear-gradient(180deg,{PEACH},{PURPLE}); }}

        @media(max-width:980px) {{
            .metric-grid, .phone-grid, .admin-grid, .admin-two, .watch-grid, .wellness-grid, .role-grid, .outcome-grid {{ grid-template-columns:1fr; }}
            .tablet-hero, .tablet-actions-grid {{ grid-template-columns:1fr; }}
            .robot-tablet {{ padding:24px; }}
            .tablet-status {{ position:static; justify-content:flex-end; margin-bottom:18px; }}
            .admin-shell, .provider-shell {{ grid-template-columns:1fr; }}
            .admin-side {{ display:none; }}
            .provider-navrail {{ min-height:auto; }}
            .provider-kpis, .provider-grid.two, .provider-grid.three, .provider-value-strip, .provider-nesto-card, .provider-nesto-stats, .provider-focus-panel, .provider-hero-card, .provider-hero-metrics, .provider-active-preview, .provider-overview-layout, .provider-topbar, .provider-table.patients, .provider-risk-chart, .robot-station-hero, .robot-station-stats, .robot-status-grid {{ grid-template-columns:1fr; }}
            .provider-nesto-robot, .provider-hero-robot {{ justify-items:start; }}
            .provider-side-stack {{ grid-template-columns:1fr; }}
            .provider-navrail {{ min-height:auto; }}
            .provider-nesto-promo {{ display:none; }}
            .provider-table.patients span {{ display:block; }}
            .risk-legend, .risk-bars, .risk-days {{ grid-column:1; }}
            .risk-legend {{ grid-row:auto; }}
            .robot-stage .nesto-bot {{ transform:scale(1.18); }}
            .robot-speech {{ position:static; margin:14px; max-width:none; }}
            .donut-panel {{ flex-direction:column; align-items:flex-start; }}
            .welcome-grid, .goal-panel, .setup-strip, .action-panel, .care-action-hub, .care-action-grid, .family-action-hub, .family-action-grid, .chat-workflow, .admin-action-grid, .decision-command-panel, .chat-steps, .family-landing-nav, .family-hero, .family-phone-showcase, .family-benefits, .family-how-panel, .family-security-strip, .caregiver-summary-stage, .summary-metric-grid, .summary-quick-grid, .caregiver-live-grid {{ grid-template-columns:1fr; }}
            .robot-home-setting {{ padding:22px; min-height:auto; }}
            .home-ambient {{ display:none; }}
            .home-table-base {{ left:12%; right:12%; }}
            .welcome-title {{ font-size:2.7rem; }}
            .welcome-links {{ display:none; }}
            .welcome-robot-panel {{ grid-template-columns:1fr; }}
            .tablet-brand-row {{ max-width:60%; }}
            .tablet-status {{ position:static; justify-content:flex-end; margin:14px 0; }}
            .tablet-name {{ font-size:3.3rem; }}
            .tablet-sun {{ width:42px; height:42px; }}
            .tablet-bot-zone {{ justify-content:flex-start; padding-right:0; }}
            .tablet-bot-zone .nesto-bot {{ transform:scale(1.25); margin-right:16px; }}
            .speech-bubble:after {{ display:none; }}
            .family-nav-links {{ justify-content:flex-start; flex-wrap:wrap; gap:14px 22px; }}
            .family-download {{ justify-self:start; }}
            .family-copy h1 {{ font-size:3rem; }}
            .family-feature-grid {{ grid-template-columns:repeat(2,minmax(150px,1fr)); }}
            .family-security-strip > div {{ border-right:0; border-bottom:1px solid #d6ddcf; }}
            .family-security-strip > div:last-child {{ border-bottom:0; }}
            .landing-phone {{ min-height:auto; }}
            .caregiver-phone {{ max-width:100%; min-height:auto; border-radius:30px; padding:24px 18px 18px; }}
            .summary-greeting-row, .summary-status-card, .summary-alert-row {{ grid-template-columns:1fr; }}
            .summary-greeting-row {{ align-items:flex-start; }}
            .summary-ai-card {{ padding-right:18px; }}
            .summary-bot {{ position:static; transform:scale(.8); transform-origin:left top; margin-top:8px; }}
            .caregiver-live-panel {{ position:static; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker, title, subtitle, pill="Nesto"):
    st.markdown(
        f"""
        <div class="topbar">
            <div>
                <div class="kicker">{kicker}</div>
                <div class="title">{title}</div>
                <p class="subtitle">{subtitle}</p>
            </div>
            <div class="pill">{pill}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text, style="green"):
    return f'<span class="badge badge-{style}">{text}</span>'
