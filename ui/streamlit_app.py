"""MediGraph AI — clinical workspace (Streamlit).

A role-aware, multi-page clinical UI over the MediGraph core. It retains every
capability of the original prototype (data-source counts, live graph
visualisation, observation & provider analytics, guideline/NER linking, natural-
language and LLM Q&A) and adds patient-360 decision support, population health,
cohort building, clinical NLP, FHIR/connector interoperability and an audit
console.

Run:  streamlit run ui/streamlit_app.py
"""
from __future__ import annotations

import os
import sys

# Make the package importable when run via `streamlit run ui/streamlit_app.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from medigraph import __version__  # noqa: E402
from medigraph.config import get_settings  # noqa: E402
from medigraph.security import login as do_login  # noqa: E402
from medigraph.security import decode_jwt, read_events, record as audit_record  # noqa: E402
from medigraph.security.rbac import Permission, Role, has_permission  # noqa: E402
from medigraph.services import get_engine  # noqa: E402

st.set_page_config(page_title="MediGraph AI", page_icon="🩺", layout="wide")

# --------------------------------------------------------------------------- CSS
st.markdown(
    """
    <style>
      .stApp { background-color:#0b1220; color:#e8eef9; }
      section[data-testid="stSidebar"] { background-color:#0f1a2e; }
      h1,h2,h3,h4 { color:#f1f6ff !important; }
      .stMetric { background:#13203a; border:1px solid #1e2f52; border-radius:14px; padding:10px; }
      .pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600; }
      .pill-high { background:#7f1d1d; color:#fecaca; }
      .pill-moderate { background:#78350f; color:#fde68a; }
      .pill-low { background:#14532d; color:#bbf7d0; }
      .pill-supported { background:#14532d; color:#bbf7d0; }
      .pill-config { background:#1e3a8a; color:#bfdbfe; }
      .pill-roadmap { background:#3f3f46; color:#e4e4e7; }
      .card { background:#13203a; border:1px solid #1e2f52; border-radius:14px; padding:16px; margin-bottom:10px; }
      .stButton>button { background:linear-gradient(90deg,#0ea5e9,#38bdf8); color:#06121f; font-weight:700;
                         border:none; border-radius:999px; padding:8px 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def engine():
    return get_engine()


def pill(text: str, kind: str) -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


# --------------------------------------------------------------------------- Auth
def auth_block():
    s = get_settings()
    st.sidebar.markdown(f"### 🩺 {s.app_name}")
    st.sidebar.caption(s.app_tagline)
    st.sidebar.caption(f"v{__version__} · {s.mode_summary}")

    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user:
        u = st.session_state.user
        st.sidebar.success(f"Signed in: {u['name']} ({u['role']})")
        if st.sidebar.button("Sign out"):
            st.session_state.user = None
            st.rerun()
        return

    with st.sidebar.expander("🔐 Sign in", expanded=True):
        st.caption("Demo logins — clinician / nurse / analyst / admin / auditor (password = role+123, e.g. `clinician123`).")
        username = st.text_input("Username", value="dr.house")
        password = st.text_input("Password", value="clinician123", type="password")
        c1, c2 = st.columns(2)
        if c1.button("Sign in"):
            token = do_login(username, password)
            if token:
                claims = decode_jwt(token)
                st.session_state.user = {"name": claims["name"], "role": claims["role"],
                                         "username": claims["sub"], "token": token}
                st.rerun()
            else:
                st.error("Invalid credentials.")
        if c2.button("Demo clinician"):
            token = do_login("dr.house", "clinician123")
            claims = decode_jwt(token)
            st.session_state.user = {"name": claims["name"], "role": claims["role"],
                                     "username": claims["sub"], "token": token}
            st.rerun()


def role() -> Role:
    u = st.session_state.get("user")
    return Role(u["role"]) if u else None


def can(p: Permission) -> bool:
    r = role()
    return bool(r) and has_permission(r, p)


# --------------------------------------------------------------------------- Pages
def page_overview():
    s = get_settings()
    eng = engine()
    st.title("MediGraph AI")
    st.markdown(f"**{s.app_tagline}** — running in **{s.mode_summary}**.")

    stats = eng.stats()
    cols = st.columns(6)
    labels = ["Patient", "Encounter", "Condition", "Medication", "Provider", "Observation"]
    for col, lab in zip(cols, labels):
        col.metric(f"{lab}s", f"{stats.node_counts.get(lab, 0):,}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("What this platform does")
        st.markdown(
            "- **Patient 360 & decision support** — risk scores, care gaps, drug interactions\n"
            "- **Population health & cohorts** — prevalence, quality measures, registries\n"
            "- **Knowledge graph** — live subgraph + provider network analytics\n"
            "- **Clinical NLP** — entity extraction with negation + guideline linking\n"
            "- **GraphRAG Q&A** — grounded answers with citations & read-only guardrails\n"
            "- **Interoperability** — FHIR R4, HL7 v2, C-CDA, US + India connectors")
    with c2:
        st.subheader("Population risk snapshot")
        rs = eng.risk_stratification()
        bands = rs["lace_bands"]
        st.markdown(
            f"{pill('High', 'high')} {bands.get('high',0)} &nbsp; "
            f"{pill('Moderate', 'moderate')} {bands.get('moderate',0)} &nbsp; "
            f"{pill('Low', 'low')} {bands.get('low',0)} &nbsp; readmission risk (LACE)",
            unsafe_allow_html=True)
        st.metric("Open care gaps (population)", rs["total_care_gaps"])
        st.metric("Drug-interaction alerts", rs["total_interactions"])
    st.info("Tip: sign in as different roles (sidebar) to see role-based access control in action.")


def page_patient360():
    eng = engine()
    st.title("Patient 360 & Decision Support")
    if not can(Permission.VIEW_PHI) and not can(Permission.VIEW_DEIDENTIFIED):
        st.warning("Sign in to view patient data.")
        return

    patients = eng.list_patients()
    query = st.text_input("Search patient by name or ID", "")
    options = [p for p in patients if query.lower() in p.full_name.lower() or query.lower() in p.id.lower()] or patients
    labels = {f"{p.full_name} · {p.id} · {p.country}": p.id for p in options[:200]}
    choice = st.selectbox("Patient", list(labels.keys()))
    pid = labels[choice]
    rec = eng.record(pid)
    if not rec:
        st.error("Patient not found."); return

    if can(Permission.VIEW_PHI):
        audit_record(st.session_state.user["username"], role().value, "view_patient",
                     resource=f"Patient/{pid}", patient_id=pid)

    p = rec.patient
    show_phi = can(Permission.VIEW_PHI)
    name = p.full_name if show_phi else f"De-identified · {p.sex.value}, {p.age}y"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patient", name if show_phi else "REDACTED")
    c2.metric("Age / Sex", f"{p.age} · {p.sex.value}")
    c3.metric("Location", f"{(p.city + ', ') if (p.city and show_phi) else ''}{p.state or ''} ({p.country})")
    c4.metric("Identifier", (p.mrn or p.abha_id or p.id) if show_phi else "REDACTED")

    assess = eng.assess(pid)
    st.markdown("### 🧮 Risk scores")
    rc = st.columns(max(1, len(assess.risk_scores)))
    for col, sc in zip(rc, assess.risk_scores):
        col.markdown(
            f'<div class="card"><b>{sc.name}</b><br><span style="font-size:1.8rem">{sc.score}{(" "+sc.unit) if sc.unit else ""}</span>'
            f'<br>{pill(sc.risk_band.title(), sc.risk_band)}<br><span style="font-size:0.8rem">{sc.interpretation}</span></div>',
            unsafe_allow_html=True)

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("### ⚠️ Care gaps")
        if assess.care_gaps:
            for g in assess.care_gaps:
                st.markdown(
                    f'<div class="card">{pill(g.severity.title(), g.severity)} <b>{g.title}</b><br>'
                    f'{g.detail}<br><i>→ {g.recommendation}</i><br>'
                    f'<span style="font-size:0.75rem;color:#9fb3d1">Guideline: {g.guideline}</span></div>',
                    unsafe_allow_html=True)
        else:
            st.success("No open care gaps detected.")
    with cc2:
        st.markdown("### 💊 Drug interactions")
        if assess.interactions:
            for ix in assess.interactions:
                st.markdown(
                    f'<div class="card">{pill(ix.severity.title(), "high" if ix.severity in ("major","contraindicated") else "moderate")} '
                    f'<b>{ix.drug_a} + {ix.drug_b}</b><br>{ix.mechanism}<br><i>→ {ix.management}</i></div>',
                    unsafe_allow_html=True)
        else:
            st.success("No known drug–drug interactions.")

    st.markdown("### 📋 Clinical record")
    t1, t2, t3 = st.tabs(["Conditions", "Medications", "Observations"])
    with t1:
        st.dataframe(pd.DataFrame([{"condition": c.name, "ICD-10": c.icd10, "SNOMED": c.snomed,
                                    "status": c.clinical_status} for c in rec.conditions]),
                     use_container_width=True)
    with t2:
        st.dataframe(pd.DataFrame([{"medication": m.name, "class": m.drug_class, "RxNorm": m.rxnorm,
                                    "status": m.status} for m in rec.medications]),
                     use_container_width=True)
    with t3:
        st.dataframe(pd.DataFrame([{"observation": o.name, "value": o.value, "unit": o.unit,
                                    "interpretation": o.interpretation, "LOINC": o.loinc}
                                   for o in rec.observations[:200]]), use_container_width=True)

    if can(Permission.IMPORT_EXPORT):
        with st.expander("🔗 Export as FHIR R4 bundle"):
            st.json(eng.to_fhir(pid))


def page_population():
    eng = engine()
    st.title("Population Health & Quality")
    if not can(Permission.VIEW_ANALYTICS):
        st.warning("Your role cannot view analytics."); return

    summary = eng.population_summary()
    c = st.columns(4)
    c[0].metric("Patients", summary["patients"])
    c[1].metric("Mean age", summary["mean_age"])
    c[2].metric("Avg conditions/patient", summary["avg_conditions"])
    c[3].metric("Avg medications/patient", summary["avg_medications"])
    st.caption(f"Country mix: {summary['country_split']} · Sex: {summary['sex_split']}")

    st.markdown("### 📊 Quality measures (HEDIS-flavoured)")
    qms = eng.quality_measures()
    qdf = pd.DataFrame([{"measure": m.name, "rate_%": m.rate, "numerator": m.numerator,
                         "denominator": m.denominator} for m in qms])
    st.dataframe(qdf, use_container_width=True)
    _bar(qdf.set_index("measure")["rate_%"], "Quality measure rate (%)")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🦠 Condition prevalence")
        prev = eng.condition_prevalence().head(12)
        st.dataframe(prev, use_container_width=True)
    with c2:
        st.markdown("### 💊 Medication usage")
        st.dataframe(eng.medication_usage().head(12), use_container_width=True)

    st.markdown("### 🚑 Utilisation")
    util = eng.utilization()
    uc = st.columns(3)
    uc[0].metric("Total encounters", util["total_encounters"])
    uc[1].metric("ED visits", util["ed_visits"])
    uc[2].metric("Inpatient admissions", util["inpatient_admissions"])

    st.markdown("### 🎯 Top-priority patients for outreach")
    tp = eng.top_priority_patients(limit=15)
    if not tp.empty and not can(Permission.VIEW_PHI):
        tp = tp.drop(columns=["name"], errors="ignore")
    st.dataframe(tp, use_container_width=True)


def page_cohort():
    eng = engine()
    st.title("Cohort Builder")
    if not can(Permission.BUILD_COHORT):
        st.warning("Your role cannot build cohorts."); return
    from medigraph.services.cohort import CohortCriteria

    presets = eng.preset_registries()
    preset_name = st.selectbox("Start from a registry preset", ["— custom —"] + list(presets.keys()))

    from medigraph.domain import terminology as T
    cond_opts = {v.name: k for k, v in T.CONDITIONS.items()}
    med_opts = {v.name: k for k, v in T.MEDICATIONS.items()}

    if preset_name != "— custom —":
        res = eng.build_cohort(presets[preset_name])
    else:
        col1, col2 = st.columns(2)
        with col1:
            inc = st.multiselect("Include patients with ANY of", list(cond_opts.keys()))
            without = st.multiselect("WITHOUT medications", list(med_opts.keys()))
            country = st.selectbox("Country", ["Any", "US", "IN"])
        with col2:
            min_age = st.number_input("Min age", 0, 120, 0)
            max_age = st.number_input("Max age", 0, 120, 120)
            a1c_gate = st.checkbox("HbA1c ≥ 9")
        crit = CohortCriteria(
            any_conditions=[cond_opts[x] for x in inc],
            without_medications=[med_opts[x] for x in without],
            min_age=min_age or None, max_age=max_age if max_age < 120 else None,
            country=None if country == "Any" else country,
            lab_filters=[("hba1c", ">=", 9.0)] if a1c_gate else [],
            label="Custom cohort")
        res = eng.build_cohort(crit)

    st.markdown(f"### Result: **{res.size}** patients")
    st.write(res.summary())
    rows = []
    for r in res.records[:300]:
        rows.append({"id": r.patient.id, "name": r.patient.full_name if can(Permission.VIEW_PHI) else "REDACTED",
                     "age": r.patient.age, "sex": r.patient.sex.value, "country": r.patient.country,
                     "conditions": ", ".join(r.condition_keys)})
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.download_button("Download cohort CSV", df.to_csv(index=False), "cohort.csv", "text/csv")


def page_graph():
    eng = engine()
    st.title("Knowledge Graph")
    stats = eng.stats()
    st.caption(f"{stats.total_nodes:,} nodes · {stats.total_relationships:,} relationships · "
               f"relationship types: {', '.join(stats.relationship_counts.keys())}")

    n = st.slider("Subgraph size (patient–neighbour triples)", 25, 150, 60, 5)
    if st.button("Render live subgraph"):
        nodes, edges = eng.subgraph_elements(limit=n)
        html = _vis_html(nodes, edges)
        st.components.v1.html(html, height=560)
    st.markdown("### 🧭 Provider network analytics (PageRank centrality + community)")
    st.caption("Mirrors a Neo4j GDS workflow: providers ranked by importance in the patient–provider network.")
    st.dataframe(eng.provider_centrality().head(15), use_container_width=True)


def page_nlp():
    eng = engine()
    st.title("Clinical NLP — Entity Extraction & Guidelines")
    if not can(Permission.RUN_QUERY):
        st.warning("Sign in to use NLP."); return
    default = ("54-year-old male with long-standing type 2 diabetes and hypertension, on metformin "
               "and lisinopril. No chest pain. Denies prior stroke. Blood pressure remains elevated.")
    text = st.text_area("Paste a clinical note", value=default, height=150)
    if st.button("Analyze note"):
        na = eng.analyze_note(text)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Detected problems")
            st.dataframe(pd.DataFrame([{"text": e.text, "system": e.code_system, "code": e.code}
                                       for e in na.problems]), use_container_width=True)
            st.markdown("#### Medications")
            st.dataframe(pd.DataFrame([{"text": e.text, "RxNorm": e.code} for e in na.medications]),
                         use_container_width=True)
            neg = [e for e in na.entities if e.negated]
            if neg:
                st.markdown("#### Negated (excluded) ✓")
                st.write(", ".join(f"{e.text}" for e in neg))
        with c2:
            st.markdown("#### Guidelines linked from the knowledge graph")
            for g in na.linked_guidelines:
                st.markdown(f'<div class="card"><b>{g["condition"]}</b> — {g["title"]}<br>'
                            f'{g["recommendation"]}<br><span style="font-size:0.75rem;color:#9fb3d1">{g["source"]}</span></div>',
                            unsafe_allow_html=True)


def page_qa():
    eng = engine()
    st.title("GraphRAG Q&A")
    st.caption("Grounded in the knowledge graph · returns citations · read-only guardrails on any generated query.")
    if not can(Permission.RUN_QUERY):
        st.warning("Sign in to ask questions."); return
    examples = ["show patients with diabetes", "how many patients have hypertension",
                "patients with atrial fibrillation not on anticoagulant", "most common conditions"]
    st.write("Examples: " + " · ".join(f"`{e}`" for e in examples))
    q = st.text_input("Ask a question", value="patients with atrial fibrillation not on anticoagulant")
    if st.button("Ask"):
        res = eng.ask(q)
        st.markdown(res.answer)
        if res.cypher:
            st.code(res.cypher, language="cypher")
        if res.data is not None and not res.data.empty:
            st.dataframe(res.data, use_container_width=True)
        if res.citations:
            st.caption("Citations: " + ", ".join(res.citations[:12]) +
                       (" …" if len(res.citations) > 12 else ""))
        st.caption(f"Intent: `{res.intent}` · grounded: {res.grounded}")


def page_interop():
    eng = engine()
    st.title("Interoperability & Connectors")
    from medigraph.connectors import CATALOG, connector_directory

    st.markdown("### 🔌 Active connectors")
    st.dataframe(pd.DataFrame(connector_directory()), use_container_width=True)

    st.markdown("### 🌐 Supported systems (US + India)")
    country = st.radio("Filter", ["All", "US", "IN", "Global"], horizontal=True)
    rows = [vars(e) for e in CATALOG if country == "All" or e.country == country]
    cat = pd.DataFrame(rows)[["name", "country", "category", "standard", "connector", "status", "notes"]]
    st.dataframe(cat, use_container_width=True)

    st.markdown("### 🧪 Try a live parse (HL7 v2 / C-CDA / FHIR)")
    if not can(Permission.IMPORT_EXPORT):
        st.info("Import/export requires the clinician or admin role.")
        return
    from medigraph.connectors import get_connector
    kind = st.selectbox("Message type", ["HL7 v2 (ORU)", "C-CDA", "FHIR bundle (JSON)"])
    samples = {
        "HL7 v2 (ORU)": ("MSH|^~\\&|LAB|HOSP|EHR|HOSP|20260601120000||ORU^R01|1|P|2.5\r"
                          "PID|1||MRN12345^^^HOSP||Doe^John||19600115|M|||123 Main St^^Boston^MA^02118\r"
                          "PV1|1|E\rDG1|1||E11.9^Type 2 diabetes mellitus^ICD-10\r"
                          "OBX|1|NM|4548-4^Hemoglobin A1c^LN||9.2|%|||||F|||20260601"),
        "C-CDA": ('<?xml version="1.0"?><ClinicalDocument xmlns="urn:hl7-org:v3"><recordTarget>'
                  '<patientRole><id extension="CCD-77"/><patient><name><given>Asha</given>'
                  '<family>Patel</family></name><administrativeGenderCode code="F"/></patient>'
                  '<addr><city>Chennai</city><state>TN</state></addr></patientRole></recordTarget>'
                  '<component><structuredBody><component><section><code code="11450-4"/><entry>'
                  '<observation><value code="59621000" displayName="Essential hypertension"/>'
                  '</observation></entry></section></component></structuredBody></component></ClinicalDocument>'),
        "FHIR bundle (JSON)": "",
    }
    payload = st.text_area("Payload", value=samples[kind], height=160)
    if st.button("Parse → canonical record"):
        try:
            if kind == "HL7 v2 (ORU)":
                rec = get_connector("hl7v2").ingest(payload)
            elif kind == "C-CDA":
                rec = get_connector("ccda").ingest(payload)
            else:
                import json
                rec = get_connector("fhir").ingest(json.loads(payload))
            st.success(f"Parsed: {rec.patient.full_name} ({rec.patient.country})")
            st.write({"conditions": [c.name for c in rec.conditions],
                      "medications": [m.name for m in rec.medications],
                      "observations": [(o.name, o.value, o.unit) for o in rec.observations]})
        except Exception as exc:
            st.error(f"Parse failed: {exc}")


def page_admin():
    st.title("Admin & Audit")
    if not (can(Permission.VIEW_AUDIT) or can(Permission.MANAGE_USERS)):
        st.warning("Your role cannot view the audit console."); return
    from medigraph.security import get_user_store
    st.markdown("### 👥 Users & roles")
    st.dataframe(pd.DataFrame([{"username": u.username, "name": u.full_name, "role": u.role.value}
                               for u in get_user_store().list_users()]), use_container_width=True)
    st.markdown("### 📜 Audit trail (most recent)")
    events = read_events(limit=200)
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True)
    else:
        st.info("No audit events yet — browse a patient to generate some.")


# --------------------------------------------------------------------------- helpers
def _bar(series, title):
    try:
        import plotly.express as px
        fig = px.bar(series, title=title)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#e8eef9", showlegend=False, height=320)
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.bar_chart(series)


def _vis_html(nodes, edges) -> str:
    import json
    nodes_js = json.dumps(nodes)
    edges_js = json.dumps(edges)
    return f"""
    <div id="net" style="height:520px;background:#0b1220;border-radius:14px;"></div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
    <script>
      var nodes = new vis.DataSet({nodes_js});
      var edges = new vis.DataSet({edges_js});
      new vis.Network(document.getElementById('net'), {{nodes:nodes, edges:edges}}, {{
        nodes:{{shape:'dot', size:14, font:{{color:'#e8eef9'}}}},
        edges:{{color:'#33415c', arrows:'to', font:{{size:9, color:'#8fa6c8'}}}},
        physics:{{stabilization:true, barnesHut:{{gravitationalConstant:-8000}}}}
      }});
    </script>
    """


PAGES = {
    "🏠 Overview": page_overview,
    "🧑‍⚕️ Patient 360": page_patient360,
    "📈 Population Health": page_population,
    "👥 Cohort Builder": page_cohort,
    "🕸️ Knowledge Graph": page_graph,
    "📝 Clinical NLP": page_nlp,
    "💬 GraphRAG Q&A": page_qa,
    "🔌 Interoperability": page_interop,
    "🛡️ Admin & Audit": page_admin,
}


def main():
    auth_block()
    st.sidebar.markdown("---")
    choice = st.sidebar.radio("Navigate", list(PAGES.keys()))
    if st.session_state.get("user") is None and choice not in ("🏠 Overview", "🔌 Interoperability"):
        st.info("👈 Sign in from the sidebar (or click **Demo clinician**) to use this section.")
        page_overview()
        return
    PAGES[choice]()


if __name__ == "__main__":
    main()
