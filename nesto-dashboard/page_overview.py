"""
Landing/product overview page for NESTO Care.
"""

import streamlit as st
import streamlit.components.v1 as components


def render():
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"],
            div[data-testid="stSidebarCollapsedControl"] {
                display: none !important;
            }
            .block-container {
                max-width: 1030px !important;
                padding: 8px !important;
            }
            .stApp {
                background: #f4f1eb !important;
            }
            iframe[title="st.iframe"] {
                display: block;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    components.html(_landing_html(), height=710, scrolling=False)


def _landing_html():
    nav_items = [
        ("&#8962;", "Home", "home", "active"),
        ("&#9881;", "Features", "features", ""),
        ("&#128279;", "How it works", "how", ""),
        ("&#128172;", "About Nesto", "about", ""),
        ("?", "FAQ", "faq", ""),
        ("&#128274;", "Privacy Policy", "privacy", ""),
        ("&#9635;", "Terms of Service", "terms", ""),
        ("&#128222;", "Contact Us", "contact", ""),
    ]
    features = [
        ("&#129302;", "Companion", "Friendly conversations and emotional support", "#e9f2ec"),
        ("&#128203;", "Reminders", "Medication, activities, and daily routines", "#fff0e8"),
        ("&#128737;", "Safety", "Emergency alerts and safety monitoring", "#eef1f4"),
        ("&#128101;", "Connection", "Keep family and caregivers in the loop", "#eaf5ff"),
        ("&#128155;", "AI Powered", "Understands, learns, and adapts to you", "#fff4d9"),
    ]
    nav_html = "".join(
        f'<a class="nav-item {active}" href="#{target}" data-target="{target}"><span>{icon}</span>{label}</a>'
        for icon, label, target, active in nav_items
    )
    feature_html = "".join(
        f"""
        <article class="feature-card">
            <span class="feature-icon" style="background:{color};">{icon}</span>
            <b>{title}</b>
            <p>{copy}</p>
        </article>
        """
        for icon, title, copy, color in features
    )
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{
                box-sizing: border-box;
            }}
            :root {{
                --nesto-brand-pattern: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150' fill='none'%3E%3Cg stroke-linecap='round' stroke-linejoin='round' stroke-width='2.6'%3E%3Cpath d='M23 42 36 31l13 11v19H27V45' stroke='%23A8BFAE'/%3E%3Cpath d='M35 61V49h8v12' stroke='%23A8BFAE'/%3E%3Cpath d='M95 30c5-8 18-2 14 8-2 7-10 12-14 16-5-4-13-9-15-16-4-10 9-16 15-8Z' stroke='%236FA7A6'/%3E%3Cpath d='M30 103c13-4 23-13 28-25 5 15-3 29-17 35-7 3-15 2-20-1 2-4 5-7 9-9Z' stroke='%238FA3B2'/%3E%3Cpath d='M43 94c-6 4-11 9-15 16' stroke='%238FA3B2'/%3E%3Cpath d='M105 91l20 8v12c0 13-9 22-20 27-11-5-20-14-20-27V99l20-8Z' stroke='%23E6D7BF'/%3E%3Cpath d='m96 114 7 7 14-16' stroke='%23A8BFAE'/%3E%3Cpath d='M129 48h10M134 43v10' stroke='%23E6D7BF'/%3E%3Ccircle cx='68' cy='126' r='5' stroke='%236FA7A6'/%3E%3C/g%3E%3C/svg%3E");
            }}
            .nesto-brand-pattern,
            .nesto-pattern-surface {{
                position: relative;
                overflow: hidden;
            }}
            .nesto-brand-pattern::before,
            .nesto-pattern-surface::before {{
                content: "";
                position: absolute;
                inset: 0;
                background-image: var(--nesto-brand-pattern);
                background-size: 150px 150px;
                background-repeat: repeat;
                opacity: .085;
                pointer-events: none;
                z-index: 0;
            }}
            .nesto-pattern-soft::before {{
                opacity: .06;
            }}
            .nesto-brand-pattern > *,
            .nesto-pattern-surface > * {{
                position: relative;
                z-index: 1;
            }}
            html,
            body {{
                width: 100%;
                height: 100%;
                margin: 0;
                overflow: hidden;
                background-color: #f4f1eb;
                background-image: var(--nesto-brand-pattern);
                background-repeat: repeat;
                background-size: 160px 160px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                color: #123536;
            }}
            body::before {{
                content: "";
                position: fixed;
                inset: 0;
                background: rgba(244,241,235,.88);
                pointer-events: none;
            }}
            .app-shell {{
                position: relative;
                width: 100%;
                height: 694px;
                max-height: 694px;
                border: 1px solid #e7ded0;
                border-radius: 18px;
                background: rgba(255,255,255,.9);
                box-shadow: 0 18px 46px rgba(40,55,44,.08);
                overflow: hidden;
                display: grid;
                grid-template-columns: 230px minmax(0, 1fr);
            }}
            .sidebar {{
                border-right: 1px solid #eee5d9;
                padding: 24px 22px 18px;
                display: flex;
                flex-direction: column;
                min-width: 0;
            }}
            .brand {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 24px;
                font-size: .98rem;
                font-weight: 950;
            }}
            .brand span {{
                font-size: 1.75rem;
                line-height: 1;
            }}
            .nav {{
                display: grid;
                gap: 7px;
            }}
            .nav-item {{
                min-height: 36px;
                border-radius: 8px;
                padding: 0 10px;
                display: flex;
                align-items: center;
                gap: 10px;
                color: #25413f;
                text-decoration: none;
                font-size: .82rem;
                font-weight: 700;
                transition: background .15s ease, transform .15s ease;
            }}
            .nav-item:hover {{
                background: #f2f7f3;
                transform: translateX(1px);
            }}
            .nav-item.active {{
                background: #e7f1eb;
                font-weight: 850;
            }}
            .nav-item span {{
                width: 16px;
                text-align: center;
                font-size: .95rem;
            }}
            .sidebar-robot-card {{
                margin-top: auto;
                min-height: 176px;
                border: 0;
                border-radius: 0;
                background: transparent;
                display: grid;
                grid-template-rows: 122px auto;
                gap: 4px;
                place-items: center;
                padding: 8px 10px 0;
                overflow: visible;
            }}
            .sidebar-robot-card .robot {{
                transform: scale(.46);
                transform-origin: center center;
                animation: nestoFloatSmall 4s ease-in-out infinite;
            }}
            .sidebar-robot-text {{
                text-align: center;
                line-height: 1.25;
            }}
            .sidebar-robot-text b {{
                display: block;
                font-size: .82rem;
                color: #123536;
            }}
            .sidebar-robot-text span {{
                display: inline-flex;
                align-items: center;
                gap: 5px;
                margin-top: 4px;
                color: #176b4d;
                font-size: .72rem;
                font-weight: 850;
            }}
            .main {{
                position: relative;
                padding: 34px 26px 18px;
                display: grid;
                grid-template-rows: 292px 142px 108px;
                gap: 14px;
                overflow: hidden;
            }}
            .hero {{
                display: grid;
                grid-template-columns: 1.08fr .92fr;
                gap: 28px;
                align-items: center;
            }}
            h1 {{
                margin: 0 0 16px;
                font-size: 2.34rem;
                line-height: 1.13;
                letter-spacing: 0;
                color: #123536;
                font-weight: 950;
            }}
            .copy {{
                width: min(100%, 430px);
                margin: 0;
                color: #3b5551;
                font-size: .86rem;
                line-height: 1.58;
                font-weight: 600;
            }}
            .actions {{
                display: flex;
                gap: 18px;
                margin-top: 24px;
            }}
            .button {{
                min-width: 150px;
                min-height: 46px;
                border-radius: 999px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
                font-weight: 900;
                font-size: .86rem;
                cursor: pointer;
            }}
            .button.primary {{
                color: #fff;
                background: #176b4d;
                box-shadow: 0 14px 28px rgba(23,107,77,.22);
            }}
            .button.secondary {{
                color: #123536;
                background: #fff;
                border: 1px solid #e3d8c7;
            }}
            .hero-art {{
                position: relative;
                height: 100%;
                display: flex;
                align-items: flex-end;
                justify-content: center;
                padding-bottom: 18px;
            }}
            .hero-robot-visual {{
                border: 0;
                background: transparent;
                padding: 0;
                cursor: default;
                pointer-events: none;
                transform-origin: center bottom;
                transition: transform .22s ease, filter .22s ease;
            }}
            .hero-robot-visual .robot {{
                animation: nestoFloat 3.4s ease-in-out infinite;
            }}
            .hero-robot-visual .robot-shadow {{
                animation: nestoShadow 3.4s ease-in-out infinite;
            }}
            .hero-robot-visual .eye {{
                animation: nestoBlink 5.8s ease-in-out infinite;
                transform-origin: center;
            }}
            .hero-robot-visual .arm.left {{
                animation: nestoIdleWave 3.8s ease-in-out infinite;
            }}
            .sidebar-robot-card .robot {{
                animation: nestoFloatSmall 4s ease-in-out infinite;
            }}
            .speech {{
                position: absolute;
                top: 10px;
                left: 22px;
                border: 1px solid #e3d8c7;
                border-radius: 16px;
                background: #fff;
                box-shadow: 0 10px 26px rgba(37,65,63,.11);
                padding: 13px 17px;
                color: #123536;
                font-size: .78rem;
                line-height: 1.42;
                font-weight: 800;
                z-index: 3;
                cursor: pointer;
                transition: border-color .18s ease, background .18s ease, transform .18s ease;
            }}
            .speech:hover {{
                background: #fbfffc;
                border-color: #9bbda5;
                transform: translateY(-2px);
            }}
            .features {{
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 8px;
            }}
            .features.highlight .feature-card {{
                border-color: #9bbda5;
                box-shadow: 0 0 0 2px rgba(127,169,140,.15), 0 4px 16px rgba(37,65,63,.05);
            }}
            .feature-card {{
                border: 1px solid #e3d8c7;
                border-radius: 10px;
                background: #fff;
                padding: 16px 9px 10px;
                text-align: center;
                box-shadow: 0 4px 16px rgba(37,65,63,.05);
                overflow: hidden;
                transition: border-color .18s ease, box-shadow .18s ease;
            }}
            .feature-icon {{
                width: 48px;
                height: 48px;
                border-radius: 999px;
                display: grid;
                place-items: center;
                margin: 0 auto 10px;
                font-size: 1.12rem;
            }}
            .feature-card b {{
                display: block;
                color: #123536;
                font-size: .82rem;
                margin-bottom: 5px;
            }}
            .feature-card p {{
                margin: 0;
                color: #60736f;
                font-size: .65rem;
                line-height: 1.34;
            }}
            .privacy {{
                border: 1px solid #e3d8c7;
                border-radius: 14px;
                background: linear-gradient(135deg, #fffdf8, #f4f8f2);
                padding: 20px 24px;
                transition: border-color .18s ease, box-shadow .18s ease;
            }}
            .privacy.highlight {{
                border-color: #9bbda5;
                box-shadow: 0 0 0 2px rgba(127,169,140,.15);
            }}
            .privacy b {{
                display: block;
                margin-bottom: 8px;
                color: #123536;
                font-size: .95rem;
            }}
            .privacy p {{
                margin: 0 0 10px;
                color: #3d5550;
                font-size: .82rem;
                line-height: 1.45;
                font-weight: 600;
            }}
            .privacy a {{
                color: #176b4d;
                text-decoration: none;
                font-weight: 900;
                font-size: .8rem;
            }}
            .info-panel,
            .assistant-panel {{
                position: absolute;
                right: 26px;
                bottom: 24px;
                width: min(360px, calc(100% - 52px));
                border: 1px solid #d8cfc1;
                border-radius: 16px;
                background: rgba(255,255,255,.98);
                box-shadow: 0 18px 42px rgba(37,65,63,.16);
                padding: 16px;
                z-index: 12;
                opacity: 0;
                pointer-events: none;
                transform: translateY(10px);
                transition: opacity .18s ease, transform .18s ease;
            }}
            .info-panel.open,
            .assistant-panel.open {{
                opacity: 1;
                pointer-events: auto;
                transform: translateY(0);
            }}
            .panel-head {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 8px;
            }}
            .panel-head b {{
                color: #123536;
                font-size: .98rem;
            }}
            .panel-close {{
                border: 1px solid #dce9df;
                background: #eef5f1;
                color: #123536;
                width: 30px;
                height: 30px;
                border-radius: 999px;
                cursor: pointer;
                font-weight: 950;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                transition: background .16s ease, transform .16s ease, border-color .16s ease;
            }}
            .panel-close:hover {{
                background: #e1efe7;
                border-color: #a9c7b3;
                transform: translateY(-1px);
            }}
            .panel-copy {{
                color: #4a625e;
                font-size: .82rem;
                line-height: 1.5;
                margin: 0;
                font-weight: 650;
            }}
            .assistant-actions {{
                display: flex;
                gap: 10px;
                margin-top: 14px;
                flex-wrap: wrap;
            }}
            .assistant-actions a,
            .assistant-actions button {{
                border: 1px solid #d8cfc1;
                border-radius: 999px;
                min-height: 36px;
                padding: 0 14px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: #fff;
                color: #123536;
                text-decoration: none;
                font-weight: 850;
                font-size: .78rem;
                cursor: pointer;
            }}
            .assistant-actions a {{
                background: #176b4d;
                color: #fff;
                border-color: #176b4d;
            }}
            .start-panel {{
                position: absolute;
                inset: 0;
                z-index: 22;
                display: grid;
                place-items: center;
                padding: 24px;
                background: rgba(18,53,54,.18);
                backdrop-filter: blur(1px);
                opacity: 0;
                pointer-events: none;
                transition: opacity .18s ease;
            }}
            .start-panel.open {{
                opacity: 1;
                pointer-events: auto;
            }}
            .start-card {{
                position: relative;
                width: min(720px, 100%);
                border: 1px solid #e2d7c8;
                border-radius: 20px;
                background: #fffdf8;
                box-shadow: 0 24px 64px rgba(37,65,63,.22);
                padding: 24px;
                overflow: hidden;
            }}
            .start-card::before {{
                content: "";
                position: absolute;
                inset: 0;
                background: radial-gradient(circle at 82% 24%, rgba(127,169,140,.16), transparent 34%);
                pointer-events: none;
            }}
            .start-panel .panel-close {{
                position: absolute;
                top: 14px;
                right: 14px;
                z-index: 2;
                background: #f3faf5;
            }}
            .start-modal-grid {{
                position: relative;
                z-index: 1;
                display: grid;
                grid-template-columns: minmax(0, 1fr) 178px;
                gap: 24px;
                align-items: center;
            }}
            .start-kicker {{
                display: inline-flex;
                align-items: center;
                min-height: 24px;
                border-radius: 999px;
                background: #e7f1eb;
                color: #176b4d;
                padding: 0 10px;
                font-size: .72rem;
                font-weight: 900;
                margin-bottom: 10px;
            }}
            .start-copy h2 {{
                margin: 0;
                color: #123536;
                font-size: 1.55rem;
                line-height: 1.08;
                letter-spacing: 0;
            }}
            .start-copy .panel-copy {{
                margin-top: 10px;
                max-width: 390px;
            }}
            .start-choice {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-top: 18px;
            }}
            .start-option,
            .role-card,
            .back-button {{
                border: 1px solid #d8cfc1;
                border-radius: 16px;
                background: #fffdf8;
                color: #123536;
                min-height: 78px;
                padding: 14px;
                text-decoration: none;
                text-align: left;
                cursor: pointer;
                font-family: inherit;
                box-shadow: 0 10px 24px rgba(37,65,63,.06);
                display: flex;
                flex-direction: column;
                justify-content: center;
                gap: 5px;
                transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease, background .16s ease;
            }}
            .start-option:hover,
            .role-card:hover,
            .back-button:hover {{
                transform: translateY(-2px);
                border-color: #9bbda5;
                box-shadow: 0 16px 30px rgba(37,65,63,.11);
            }}
            .start-option b,
            .role-card b {{
                font-size: .86rem;
                font-weight: 950;
            }}
            .start-option small,
            .role-card small {{
                color: #60736f;
                font-size: .68rem;
                line-height: 1.35;
                font-weight: 700;
            }}
            .start-option.primary {{
                background: #176b4d;
                border-color: #176b4d;
                color: #fff;
            }}
            .start-option.primary small {{
                color: rgba(255,255,255,.82);
            }}
            .start-option.secondary {{
                background: #fffdf8;
                border-color: #b8d2c0;
            }}
            .start-option-icon {{
                width: 28px;
                height: 28px;
                display: inline-grid;
                place-items: center;
                border-radius: 999px;
                background: rgba(127,169,140,.16);
                margin-bottom: 2px;
                font-size: .9rem;
            }}
            .start-option.primary .start-option-icon {{
                background: rgba(255,255,255,.16);
            }}
            .demo-login {{
                display: none;
                margin-top: 18px;
            }}
            .demo-login.open {{
                display: block;
            }}
            .demo-continue {{
                display: none;
                margin-top: 18px;
            }}
            .demo-continue.open {{
                display: block;
            }}
            .role-heading {{
                margin-bottom: 12px;
            }}
            .role-heading b {{
                display: block;
                color: #123536;
                font-size: .98rem;
                font-weight: 950;
            }}
            .role-heading span {{
                display: block;
                color: #60736f;
                font-size: .72rem;
                line-height: 1.4;
                margin-top: 3px;
                font-weight: 700;
            }}
            .role-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
            }}
            .role-card {{
                min-height: 104px;
                align-items: flex-start;
            }}
            .role-icon {{
                width: 30px;
                height: 30px;
                display: inline-grid;
                place-items: center;
                border-radius: 999px;
                background: #e7f1eb;
                color: #176b4d;
                margin-bottom: 3px;
                font-size: 1rem;
            }}
            .back-button {{
                min-height: 36px;
                width: max-content;
                border-radius: 999px;
                padding: 0 14px;
                margin-top: 12px;
                font-size: .76rem;
                font-weight: 900;
                flex-direction: row;
                align-items: center;
                justify-content: center;
                box-shadow: none;
            }}
            .demo-profile-card {{
                border: 1px solid #d8cfc1;
                border-radius: 16px;
                background: #fffdf8;
                padding: 14px;
                color: #123536;
                box-shadow: 0 10px 24px rgba(37,65,63,.06);
                display: grid;
                gap: 8px;
            }}
            .demo-profile-card b {{
                display: block;
                font-size: .92rem;
                font-weight: 950;
            }}
            .demo-profile-card span {{
                color: #60736f;
                font-size: .76rem;
                line-height: 1.4;
                font-weight: 750;
            }}
            .account-picker {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-top: 4px;
            }}
            .linked-account-card {{
                border: 1px solid #d8cfc1;
                border-radius: 14px;
                background: rgba(255,253,248,.9);
                color: #123536;
                padding: 10px 11px;
                text-align: left;
                cursor: pointer;
                font: inherit;
                display: grid;
                gap: 3px;
                box-shadow: 0 8px 18px rgba(37,65,63,.05);
            }}
            .linked-account-card b {{
                font-size: .8rem;
            }}
            .linked-account-card span {{
                font-size: .68rem;
                line-height: 1.3;
            }}
            .linked-account-card.selected {{
                border-color: #176b4d;
                background: #e9f4ed;
                box-shadow: 0 10px 22px rgba(23,107,77,.11);
            }}
            .demo-actions {{
                display: grid;
                grid-template-columns: 1fr 1.25fr;
                gap: 10px;
                margin-top: 12px;
            }}
            .demo-actions button {{
                min-height: 42px;
                border-radius: 999px;
                font: inherit;
                font-size: .8rem;
                font-weight: 950;
                cursor: pointer;
                border: 1px solid #176b4d;
            }}
            .demo-actions .secondary {{
                background: #fffdf8;
                color: #123536;
            }}
            .demo-actions .primary {{
                background: #176b4d;
                color: #fff;
                box-shadow: 0 12px 24px rgba(23,107,77,.16);
            }}
            .start-robot-wrap {{
                align-self: stretch;
                display: grid;
                place-items: center;
                gap: 10px;
                border: 0;
                border-radius: 0;
                background: transparent;
                padding: 10px 6px;
                overflow: visible;
            }}
            .start-speech {{
                border: 1px solid #e2d7c8;
                border-radius: 14px;
                background: #fff;
                box-shadow: 0 10px 22px rgba(37,65,63,.08);
                color: #123536;
                padding: 10px 12px;
                font-size: .74rem;
                line-height: 1.35;
                font-weight: 900;
                text-align: center;
            }}
            .modal-robot {{
                width: 132px;
                height: 152px;
                display: grid;
                place-items: center;
                overflow: visible;
            }}
            .modal-robot-scale {{
                width: 116px;
                height: 138px;
                transform-origin: center center;
                animation: nestoModalFloat 4s ease-in-out infinite;
            }}
            .modal-robot .robot {{
                transform: scale(.55);
                transform-origin: top left;
            }}
            .modal-robot .robot-shadow {{
                animation: nestoShadow 4s ease-in-out infinite;
            }}
            .modal-robot .eye {{
                animation: nestoBlink 5.8s ease-in-out infinite;
            }}
            .modal-robot .arm.left {{
                animation: nestoIdleWave 3.8s ease-in-out infinite;
            }}
            .robot {{
                position: relative;
                width: 210px;
                height: 248px;
                transform: scale(.88);
                transform-origin: center bottom;
            }}
            .robot-shadow {{
                position: absolute;
                left: 38px;
                right: 38px;
                bottom: 7px;
                height: 18px;
                border-radius: 999px;
                background: rgba(37,65,63,.12);
                filter: blur(5px);
            }}
            .robot-head {{
                position: absolute;
                left: 49px;
                top: 28px;
                width: 112px;
                height: 92px;
                border-radius: 42px;
                background: #f7f2e8;
                border: 6px solid #e1d9ca;
                box-shadow: inset 0 -10px 0 rgba(127,169,140,.08);
            }}
            .robot-face {{
                position: absolute;
                left: 64px;
                top: 47px;
                width: 82px;
                height: 54px;
                border-radius: 23px;
                background: #183c3d;
            }}
            .eye {{
                position: absolute;
                top: 15px;
                width: 13px;
                height: 20px;
                border-radius: 999px;
                background: #89f0cd;
            }}
            .eye.left {{ left: 19px; }}
            .eye.right {{ right: 19px; }}
            .smile {{
                position: absolute;
                left: 34px;
                bottom: 10px;
                width: 16px;
                height: 8px;
                border-bottom: 3px solid #89f0cd;
                border-radius: 0 0 999px 999px;
            }}
            .ear {{
                position: absolute;
                top: 57px;
                width: 18px;
                height: 42px;
                border-radius: 12px;
                background: #91ad8f;
                border: 4px solid #d8d0c0;
            }}
            .ear.left {{ left: 30px; }}
            .ear.right {{ right: 30px; }}
            .body {{
                position: absolute;
                left: 57px;
                top: 117px;
                width: 96px;
                height: 92px;
                border-radius: 42px 42px 30px 30px;
                background: #f8f2e7;
                border: 5px solid #e1d9ca;
            }}
            .heart {{
                position: absolute;
                left: 96px;
                top: 150px;
                color: #7fa98c;
                font-size: 24px;
                transform: translateX(-50%);
            }}
            .base {{
                position: absolute;
                left: 62px;
                bottom: 17px;
                width: 86px;
                height: 28px;
                border-radius: 12px 12px 20px 20px;
                background: #91ad8f;
            }}
            .arm {{
                position: absolute;
                width: 24px;
                height: 70px;
                top: 132px;
                border-radius: 999px;
                background: #ddd5c6;
            }}
            .arm.left {{
                left: 30px;
                transform: rotate(16deg);
                transform-origin: top center;
            }}
            .arm.right {{
                right: 26px;
                transform: rotate(-24deg);
            }}
            .hero-art .arm.left {{
                top: 98px;
                left: 22px;
                transform: rotate(-42deg);
            }}
            @keyframes waveArm {{
                0%, 100% {{ transform: rotate(-42deg); }}
                50% {{ transform: rotate(-58deg); }}
            }}
            @keyframes nestoFloat {{
                0%, 100% {{ transform: scale(.88) translateY(0); }}
                50% {{ transform: scale(.88) translateY(-7px); }}
            }}
            @keyframes nestoFloatSmall {{
                0%, 100% {{ transform: scale(.46) translateY(0); }}
                50% {{ transform: scale(.46) translateY(-4px); }}
            }}
            @keyframes nestoShadow {{
                0%, 100% {{ transform: scaleX(1); opacity: .9; }}
                50% {{ transform: scaleX(.82); opacity: .55; }}
            }}
            @keyframes nestoBlink {{
                0%, 92%, 100% {{ transform: scaleY(1); }}
                94%, 96% {{ transform: scaleY(.12); }}
            }}
            @keyframes nestoIdleWave {{
                0%, 100% {{ transform: rotate(-42deg); }}
                50% {{ transform: rotate(-50deg); }}
            }}
        </style>
    </head>
    <body>
        <section class="app-shell" data-testid="landing-single-shell">
            <aside class="sidebar" aria-label="Nesto Care navigation">
                <div class="brand"><span>&#127968;</span><b>Nesto Care</b></div>
                <nav class="nav">{nav_html}</nav>
                <div class="sidebar-robot-card">
                    {_robot_html()}
                    <div class="sidebar-robot-text"><b>Nesto is ready</b><span>&#9679; Online</span></div>
                </div>
            </aside>
            <main class="main" id="home">
                <section class="hero">
                    <div>
                        <h1>A calm companion<br>for safer ageing at home</h1>
                        <p class="copy">Nesto is a friendly robot assistant that helps elderly individuals live independently while keeping families connected and informed.</p>
                        <div class="actions">
                            <a class="button primary" href="#features" data-target="features">Learn more</a>
                            <button class="button secondary" type="button" data-start-flow>Get started</button>
                        </div>
                    </div>
                    <div class="hero-art">
                        <div class="speech" role="button" tabindex="0" aria-label="Open Nesto assistant">Hello! I'm Nesto.<br>I'm here to help. <span style="color:#7fa98c;">&#9829;</span></div>
                        <div class="hero-robot-visual nesto-robot-illustration" aria-label="Nesto robot illustration">{_robot_html()}</div>
                    </div>
                </section>
                <section class="features" id="features">{feature_html}</section>
                <section class="privacy" id="privacy">
                    <b>Trusted care with privacy first</b>
                    <p>Your data is secure and used only to provide personalized care and support.</p>
                    <a href="#privacy" data-target="privacy">Read our Privacy Policy -&gt;</a>
                </section>
                <section class="info-panel" id="infoPanel" aria-live="polite">
                    <div class="panel-head"><b id="infoTitle">Landing section</b><button class="panel-close" type="button" data-close="infoPanel">x</button></div>
                    <p class="panel-copy" id="infoCopy"></p>
                </section>
                <section class="assistant-panel" id="assistantPanel" aria-live="polite">
                    <div class="panel-head"><b>Nesto assistant</b><button class="panel-close" type="button" data-close="assistantPanel">x</button></div>
                    <p class="panel-copy">Hi, I'm Nesto. I help with reminders, safety, family updates, and daily care.</p>
                    <div class="assistant-actions">
                        <button type="button" data-start-flow>Start setup</button>
                        <button type="button" data-target="how">Learn how it works</button>
                    </div>
                </section>
                <section class="start-panel" id="startPanel" aria-live="polite" aria-label="Get started with Nesto Care">
                    <div class="start-card">
                        <button class="panel-close" type="button" data-close="startPanel" aria-label="Close start setup">&times;</button>
                        <div class="start-modal-grid">
                            <div class="start-copy">
                                <span class="start-kicker">Nesto Care setup</span>
                                <h2>Welcome to Nesto Care</h2>
                                <p class="panel-copy">Are you setting up a new profile or continuing with an existing account?</p>
                                <div class="start-choice" id="startChoice">
                                    <button class="start-option secondary" type="button" id="existingAccountButton">
                                        <span class="start-option-icon">&#8635;</span>
                                        <b>I already have an account</b>
                                        <small>Sign in to your care dashboard.</small>
                                    </button>
                                    <button class="start-option primary" type="button" id="newProfileButton">
                                        <span class="start-option-icon">&#8594;</span>
                                        <b>I'm new. Create a profile</b>
                                        <small>Create your care profile and account.</small>
                                    </button>
                                </div>
                                <div class="demo-login" id="demoLogin" aria-hidden="true"></div>
                                <div class="demo-continue" id="demoContinue" aria-hidden="true">
                                    <div class="role-heading">
                                        <b id="demoTitle">Sign in required</b>
                                        <span>Use your Nesto account to open the correct dashboard.</span>
                                    </div>
                                    <div class="demo-profile-card" id="demoProfileCard">
                                        <b>Protected dashboard</b>
                                        <span>Sign in to continue.</span>
                                    </div>
                                    <div class="demo-actions">
                                        <button class="secondary" type="button" id="backToRoleChoice">Back</button>
                                        <button class="primary" type="button" id="continueDemoRole">Sign in</button>
                                    </div>
                                </div>
                            </div>
                            <div class="start-robot-wrap" aria-hidden="true">
                                <div class="start-speech">I'll help you get started. <span style="color:#7fa98c;">&#9829;</span></div>
                                <div class="modal-robot"><div class="modal-robot-scale">{_robot_html()}</div></div>
                            </div>
                        </div>
                    </div>
                </section>
            </main>
        </section>
        <script>
            const panels = {{
                how: {{
                    title: "How it works",
                    copy: "Nesto listens for approved care requests, supports reminders and object finding, and keeps family informed through the dashboard."
                }},
                about: {{
                    title: "About Nesto",
                    copy: "Nesto Care is a calm robot companion concept for safer ageing at home, designed around simple support, privacy, and family reassurance."
                }},
                faq: {{
                    title: "FAQ",
                    copy: "Nesto supports daily routines, reminders, family updates, safety checks, and approved assistant actions. It does not replace clinicians or emergency services."
                }},
                privacy: {{
                    title: "Privacy Policy",
                    copy: "Care profile data is used only for personalized support, reminders, family visibility, and the project experience. Sensitive information should stay consent-based."
                }},
                terms: {{
                    title: "Terms of Service",
                    copy: "Nesto Care is a project support tool. It does not diagnose conditions, change medication dosage, or act as an emergency-service replacement."
                }},
                contact: {{
                    title: "Contact Us",
                    copy: "For support, contact the Nesto Care project team or caregiver administrator for setup, support, and consent questions."
                }}
            }};
            const navLinks = Array.from(document.querySelectorAll("[data-target]"));
            const infoPanel = document.getElementById("infoPanel");
            const assistantPanel = document.getElementById("assistantPanel");
            const startPanel = document.getElementById("startPanel");
            const startChoice = document.getElementById("startChoice");
            const demoLogin = document.getElementById("demoLogin");
            const demoContinue = document.getElementById("demoContinue");
            const demoTitle = document.getElementById("demoTitle");
            const demoProfileCard = document.getElementById("demoProfileCard");
            const continueDemoRole = document.getElementById("continueDemoRole");
            const infoTitle = document.getElementById("infoTitle");
            const infoCopy = document.getElementById("infoCopy");
            const features = document.getElementById("features");
            const privacy = document.getElementById("privacy");
            let selectedDemoRole = "";
            const roleFlows = {{
                elderly: {{
                    title: "Continue as Elderly User",
                    profile: "Account profile: Elderly User 01",
                    detail: "Continue to the Elderly User Interface.",
                    route: "?auth_mode=signin"
                }},
                caregiver: {{
                    title: "Continue as Guardian / Caregiver",
                    profile: "Select Guardian / Caregiver account",
                    detail: "Choose the linked care profile to open the correct dashboard.",
                    route: "?auth_mode=signin",
                    accounts: [
                        {{
                            guardian: "Anna Smith",
                            patient: "Maria Johnson",
                            relationship: "Daughter",
                            route: "?auth_mode=signin"
                        }},
                        {{
                            guardian: "Daniel Lee",
                            patient: "Rosa Patel",
                            relationship: "Son",
                            route: "?auth_mode=signin"
                        }}
                    ]
                }},
                admin: {{
                    title: "Continue as Admin / Provider",
                    profile: "Admin account: Provider Admin",
                    detail: "Continue to the Admin / Provider Dashboard.",
                    route: "?auth_mode=signin"
                }}
            }};

            function setActive(target) {{
                document.querySelectorAll(".nav-item").forEach((item) => {{
                    item.classList.toggle("active", item.dataset.target === target);
                }});
            }}
            function closePanels() {{
                infoPanel.classList.remove("open");
                assistantPanel.classList.remove("open");
                startPanel.classList.remove("open");
            }}
            function openStartFlow() {{
                infoPanel.classList.remove("open");
                assistantPanel.classList.remove("open");
                startChoice.style.display = "grid";
                demoLogin.classList.remove("open");
                demoContinue.classList.remove("open");
                startPanel.classList.add("open");
            }}
            function flash(element) {{
                element.classList.add("highlight");
                setTimeout(() => element.classList.remove("highlight"), 1200);
            }}
            function openInfo(target) {{
                if (target === "home") {{
                    closePanels();
                    setActive("home");
                    return;
                }}
                if (target === "features") {{
                    closePanels();
                    setActive("features");
                    flash(features);
                    return;
                }}
                if (target === "privacy") {{
                    setActive("privacy");
                    flash(privacy);
                }}
                const item = panels[target];
                if (!item) return;
                assistantPanel.classList.remove("open");
                infoTitle.textContent = item.title;
                infoCopy.textContent = item.copy;
                infoPanel.classList.add("open");
                if (target !== "privacy") setActive(target);
            }}
            function navigateApp(route) {{
                let parentOrigin = "";
                try {{
                    parentOrigin = window.top.location.origin;
                }} catch (error) {{
                    parentOrigin = "";
                }}
                if ((!parentOrigin || parentOrigin === "null") && window.location.ancestorOrigins && window.location.ancestorOrigins.length) {{
                    parentOrigin = window.location.ancestorOrigins[0];
                }}
                if ((!parentOrigin || parentOrigin === "null") && document.referrer) {{
                    try {{
                        parentOrigin = new URL(document.referrer).origin;
                    }} catch (error) {{
                        parentOrigin = "";
                    }}
                }}
                if (!parentOrigin || parentOrigin === "null") {{
                    parentOrigin = window.location.origin;
                }}
                const absoluteRoute = route.startsWith("http") ? route : `${{parentOrigin}}/${{route.startsWith("?") ? route : "?" + route}}`;
                try {{
                    const parentDoc = window.parent && window.parent.document;
                    if (parentDoc && parentDoc.body) {{
                        const parentLink = parentDoc.createElement("a");
                        parentLink.href = absoluteRoute;
                        parentLink.target = "_self";
                        parentLink.style.display = "none";
                        parentDoc.body.appendChild(parentLink);
                        parentLink.click();
                        parentLink.remove();
                        return;
                    }}
                }} catch (error) {{}}
                try {{
                    window.open(absoluteRoute, "_top");
                    return;
                }} catch (error) {{}}
                try {{
                    window.top.location.href = absoluteRoute;
                    return;
                }} catch (error) {{}}
                window.location.href = absoluteRoute;
            }}
            navLinks.forEach((link) => {{
                link.addEventListener("click", (event) => {{
                    const target = link.dataset.target;
                    if (!target) return;
                    if (!link.target) event.preventDefault();
                    openInfo(target);
                }});
            }});
            document.querySelector(".speech").addEventListener("click", () => {{
                infoPanel.classList.remove("open");
                assistantPanel.classList.toggle("open");
            }});
            document.querySelector(".speech").addEventListener("keydown", (event) => {{
                if (event.key === "Enter" || event.key === " ") {{
                    event.preventDefault();
                    infoPanel.classList.remove("open");
                    assistantPanel.classList.toggle("open");
                }}
            }});
            document.querySelectorAll("[data-start-flow]").forEach((button) => {{
                button.addEventListener("click", (event) => {{
                    event.preventDefault();
                    openStartFlow();
                }});
            }});
            document.getElementById("existingAccountButton").addEventListener("click", () => {{
                navigateApp("?auth_mode=signin");
            }});
            document.getElementById("newProfileButton").addEventListener("click", () => {{
                navigateApp("?nav_role=Caregiver&nav_page=User%20Creation%20%2B%20Preferences%20Page&profile_mode=create&profile_reset=1");
            }});
            const backToStartChoice = document.getElementById("backToStartChoice");
            if (backToStartChoice) {{
                backToStartChoice.addEventListener("click", () => {{
                    demoLogin.classList.remove("open");
                    demoContinue.classList.remove("open");
                    startChoice.style.display = "grid";
                }});
            }}
            const backToRoleChoice = document.getElementById("backToRoleChoice");
            if (backToRoleChoice) {{
                backToRoleChoice.addEventListener("click", () => {{
                    demoContinue.classList.remove("open");
                    startChoice.style.display = "grid";
                }});
            }}
            continueDemoRole.addEventListener("click", () => {{
                navigateApp("?auth_mode=signin");
            }});
            document.querySelectorAll("[data-close]").forEach((button) => {{
                button.addEventListener("click", () => {{
                    document.getElementById(button.dataset.close).classList.remove("open");
                }});
            }});
        </script>
    </body>
    </html>
    """


def _robot_html():
    return """
    <div class="robot" aria-label="Nesto robot mascot">
        <div class="robot-shadow"></div>
        <div class="ear left"></div>
        <div class="ear right"></div>
        <div class="robot-head"></div>
        <div class="robot-face">
            <span class="eye left"></span>
            <span class="eye right"></span>
            <span class="smile"></span>
        </div>
        <div class="arm left"></div>
        <div class="arm right"></div>
        <div class="body"></div>
        <div class="heart">&#9829;</div>
        <div class="base"></div>
    </div>
    """
