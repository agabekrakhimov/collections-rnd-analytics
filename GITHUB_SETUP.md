# How to put this project on GitHub (and make the visuals show up)

You have two paths. **Path A (website upload)** needs no tools and is the fastest.
**Path B (git command line)** is what employers like to see you using.

---

## Path A — Upload through the GitHub website (easiest, ~5 min)

1. **Create an account** at https://github.com (if you don't have one).
2. Click the **+** (top-right) → **New repository**.
   - **Repository name:** `collections-rnd-analytics`
   - **Description:** `R&D analytics for fintech debt collections — SQL, Python, ML & NLP on recovery optimisation`
   - **Public** (so recruiters can see it).
   - **Do NOT** tick "Add a README" (you already have one).
   - Click **Create repository**.
3. On the next page click **uploading an existing file**.
4. Open the `collections-rnd-analytics` folder on your computer, select **all
   files and folders inside it**, and drag them into the browser.
   - Make sure the `outputs/charts/` folder (the PNGs) and `outputs/dashboard.html`
     are included — those are your visuals.
5. In **Commit changes**, type a message like `Initial commit` → **Commit changes**.
6. Done. Your README with all charts now renders at
   `https://github.com/<your-username>/collections-rnd-analytics`.

---

## Path B — Git command line (recommended, shows the skill)

### One-time setup
- Install Git: https://git-scm.com/downloads
- Tell Git who you are:
  ```bash
  git config --global user.name "Ogabek"
  git config --global user.email "agabekrakhimov@gmail.com"
  ```

### Push the project
From **inside** the `collections-rnd-analytics` folder:

```bash
git init
git add .
git commit -m "Collections R&D analytics: SQL, EDA, propensity model, transcript NLP"
git branch -M main
```

Create the empty repo on github.com first (steps 1–2 in Path A, still
**without** a README), copy its URL, then:

```bash
git remote add origin https://github.com/<your-username>/collections-rnd-analytics.git
git push -u origin main
```

If it asks for a password, use a **Personal Access Token** instead of your
account password: GitHub → Settings → Developer settings → Personal access
tokens → *Tokens (classic)* → Generate (tick `repo` scope) → paste it as the
password.

---

## Making sure the visuals display

- **Charts in the README:** they already use relative paths like
  `outputs/charts/01_recovery_by_bucket.png`. As long as you upload the
  `outputs/charts/` folder, GitHub renders them automatically on the repo page.
- **The interactive dashboard:** `outputs/dashboard.html` won't run *inside* the
  README (GitHub doesn't execute HTML there). Two good options:

  **Option 1 — GitHub Pages (free live link):**
  1. Repo → **Settings** → **Pages**.
  2. Under *Build and deployment* → *Source*, pick **Deploy from a branch**.
  3. Branch: **main**, folder: **/ (root)** → **Save**.
  4. After ~1 min your dashboard is live at
     `https://<your-username>.github.io/collections-rnd-analytics/outputs/dashboard.html`.
  5. Add that link near the top of your README.

  **Option 2 — screen-record / screenshot:** open `dashboard.html` locally,
  take a screenshot or short GIF, and embed it in the README. (A static
  screenshot of the dashboard is already implicitly covered by the 10 PNG charts.)

---

## Polish that impresses recruiters

- Add **topics** to the repo (right sidebar → ⚙️): `data-analytics`, `fintech`,
  `collections`, `python`, `sql`, `machine-learning`, `nlp`.
- Put the **GitHub Pages dashboard link** and the **TL;DR table** at the very top
  of the README — it's the first thing people read.
- Add the repo link to your **CV and LinkedIn** ("Featured" section on LinkedIn).
- In interviews, be ready to explain: the hypotheses you tested, why you chose
  Logistic Regression vs Gradient Boosting, and how you'd validate the
  recommendations with an A/B test on real data.
