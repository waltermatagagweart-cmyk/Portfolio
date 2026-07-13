# Walter Matagagwe — Portfolio

A single-file personal portfolio you can update anytime. No frameworks, no build step.

---

## How to VIEW it

Double-click **`index.html`** — it opens in your browser. That's it.

---

## How to UPDATE it (do this anytime)

1. Open **`index.html`** in a text editor (VS Code, Notepad++, or even Notepad).
2. Scroll down to the block that says **`const DATA = {`** — near the bottom.
   Everything on the page comes from there.
3. Change the text between the quotes. Save. Refresh the browser.

### Common edits

**Add a project** — copy one project block and paste it inside `projects: [ ]`:
```js
{
  title:"My New Project",
  status:"live",              // "live", "building", or "planned"
  blurb:"One or two sentences about what it does.",
  tags:["Python","SQL"],
  links:[{label:"GitHub", url:"https://github.com/you/repo"}]
},
```

**Add a certificate** — add a line inside `certifications: [ ]`:
```js
{year:"2026", name:"Introduction to Cybersecurity", org:"Cisco Networking Academy"},
```
(The two example lines there are "commented out" with `//`. Delete the `//` to switch them on, or just add your own.)

**Mark a diploma unit done** — find it in `units` and change its `status`:
`"done"` (green tick), `"doing"` (amber, in progress), or `"todo"`.

**Change your bio** — edit the `about` lines.

> ⚠️ Keep the commas between `{ }` blocks. If the page ever goes blank after an
> edit, you probably deleted a comma or a quote — undo (Ctrl+Z) and try again.

### Two things to fill in when ready
- In `profile`, replace `https://github.com/YOUR-USERNAME` with your real GitHub URL —
  the GitHub button appears automatically once you do.
- Drop your CV PDF (named `Walter_Matagagwe_CV.pdf`) into this folder to switch on the
  "Download CV" button.

---

## How to PUT IT ONLINE for free (GitHub Pages)

So you can send a link like `https://your-username.github.io/portfolio` on applications:

1. Create a free account at **github.com**.
2. Make a new **public** repository named `portfolio`.
3. Upload `index.html` (and your CV PDF) to it — the "Add file → Upload files" button works fine.
4. Go to the repo's **Settings → Pages**.
5. Under "Branch", pick **main** and **/ (root)**, then Save.
6. Wait ~1 minute. Your live link appears at the top of that same Pages screen.

After that, every time you edit `index.html` and upload the new version, your live
site updates automatically.

---

## What's inside
- **`index.html`** — the whole portfolio (design + your content, in one file)
- **`README.md`** — this guide
