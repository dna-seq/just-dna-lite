# Report voice: how modules and reports talk to people

Our reports are read by two audiences **with equal weight**:

1. **People without a science background.** They finished school, read carefully and want to know
   what their DNA says about them. They do not know what an allele, a diplotype or a VCF is, and they
   should never need to.
2. **Professionals**: clinicians, geneticists, bioinformaticians and module authors. They need the
   exact positions, genotypes, allele names, studies and caveats to check a result.

Neither audience is served by writing for the other. The fix is **layers**: every result is written
twice, once in plain language and once for professionals, and each layer has its own place in the
module and in the report. This guide says what goes in each layer, which field it lives in, and how
it should sound.

It exists because our first reports failed the first audience completely. A real row read
*"GA variant is associated with increased risk of hyperhomocysteinemia and thrombophilia"* beside a
column called *Weight* holding `-1.3`, and a blood-group card was headed `RHCE` with the status
*Ambiguous*, a list of diplotypes and *"Compiler notes: module_not_closed · …"*. Every word was true,
and almost nobody could read it.

## Key content first; disclaimers, warnings and privacy notes at the bottom

**The reader came for their result.** A page that opens with disclaimers, interpretation notices,
privacy text or usage instructions pushes the result below the fold and teaches people to skip text,
including the text that matters. So, without exception in layout:

- **The top of a report is the title, the module description and the results.** Nothing above them
  but the header.
- **General disclaimers, interpretation notices, research-use statements, privacy explanations and
  "how to use this page" help go to the bottom**, in *How to read this report*, after the results and
  before the reproducibility tables. They are written once there, not repeated per module.
- **Inside a result, the order is the same**: the result, what it means, then its limits. A caveat
  goes last in the conclusion, never first.

Two narrow exceptions, and neither may become a paragraph or sit above a result:

1. **A warning that changes what this result means is part of the result, not a disclaimer.**
   *"This cannot be read from your DNA file; a lab test settles it"* belongs in that result's card,
   at the end of its text.
2. **A notice attached to a control that sends data goes in the control's tooltip** (`title` and
   `aria-label`), never as visible text beside it. The AI-assistant buttons are 28 px icons; a
   sentence next to them dwarfs them and breaks the layout. The full explanation lives at the bottom.

## Three kinds of module, three report shapes

Modules answer different kinds of question, and one layout cannot serve them all. Decide the kind
first; it fixes what layer 1 looks like and what must never appear.

| Kind | Example | What the reader gets first | Must not appear | Module tables | Report partial |
|---|---|---|---|---|---|
| **Per-variant findings** | longevity, coronary, thrombophilia | a table, one plain answer per row, detail and evidence on unfold | unexplained numbers in the first view | `variants.csv` (+ `studies.csv`) | per-variant tables in `longevity_report.html.j2` |
| **Combination (a "formula")** | ABO and Rh, APOE, HFE compound carriers | one named result per gene, the rule in plain words, the possibilities when the file cannot decide | weights, scores, net weight, good/bad colours: a combined result is not a sum of parts, and group O is not "worse" than A | `haplotypes.csv` + `diplotypes.csv` | `phenotype_section.html.j2` |
| **Drug response** | ClinPGx drug annotations, CPIC diplotypes | per drug: what the result means and what to tell a doctor or pharmacist | "avoid X", dose numbers, a score | `pharm_variants.csv`, or `diplotypes.csv` with drug columns, or a metaboliser class | the drug section, grouped by drug, in `longevity_report.html.j2` |

Two further kinds exist in the format without a shape of their own yet: **"how much" results**
(repeat length, copy number, mitochondrial fraction: a measurement falling into a bin) and
**polygenic scores**, which the PRS tab handles. When one of these gets a report section, it gets its
own partial, not a branch in an existing one.

**Weights are a per-variant idea.** A phenotype module authors none (`weighting: scale: none`), and
`direction` on a combined result is used only when the whole result carries a meaning (HFE
C282Y/C282Y is a risk genotype). Where it is used, the report shows it as words, never as a score or
a colour.

**A combination module needs its rule in words.** Write a `## How this works` section in
`README.md`: how the versions of each gene combine into the result, in the same plain voice as the
conclusions. The report shows it above the result cards. The professional version of the rule (which
bases define each allele, and the full allele-pair table) is generated from `haplotypes.csv` and
`diplotypes.csv` into the More details fold, so it never needs to be written twice.

## The three layers

| Layer | Question it answers | Who it is for | Where it lives in a module | Where it shows in the report |
|---|---|---|---|---|
| **1. Result** | *What does my DNA show?* | everyone | `diplotypes.phenotype`; the first sentence of `conclusion` | card heading, first words of a row |
| **2. What it means** | *So what? How common is it? How sure are you? Is there anything practical?* | everyone | the rest of `conclusion` | the paragraph under the result |
| **3. More details** | *How exactly was this determined, and how do I check it?* | professionals | `haplotypes.csv`, `studies.csv`, `README.md`, `weighting:` | the **More details** fold, study tables, the *Technical details* section |

**Layers 1 and 2 never contain layer-3 material.** No rsIDs, HGVS names (`c.261delG`), subtype codes
(`O1`, `*2`), coordinates, statistics or tool names in a phenotype label or a conclusion.

**Every term is explained where it first appears, in that text.** Each conclusion is read on its own:
the reader sees their result and nothing else, so a term explained in another result or in *How this
works* is unexplained for them. A name a reader will meet elsewhere (the ε4 version of APOE, C282Y on
an HFE lab report, the FUT2 gene) may appear, and the same conclusion says what it is at first mention:
*"The APOE gene comes in three common versions, called ε2, ε3 and ε4. They differ from each other at
two places in the gene."* Most people do not know that ε4 is a combination of two DNA changes, or that
C282Y is a one-letter change. A term that needs no explanation because nobody outside a lab uses it
does not belong in the conclusion at all.

**Layer 3 is not a footnote.** For a professional it is the result. Keep it complete and exact:
positions on GRCh38, observed genotypes, how each site was read, which alleles the module considers,
what it cannot see, and the literature. It is folded so it does not bury layer 2, not so it can be
sloppy.

## Where each module field ends up

| Field | Shown as | Write it as |
|---|---|---|
| `module.title` | report and card title | plain name of the topic: *Blood Groups (ABO and Rh)* |
| `module.description` | subtitle under the title, catalog card | one plain sentence, 5 to 15 words: *Your ABO blood group and Rh markers, read from several DNA positions.* |
| `module.report_title` | report heading for a single-module run | same as `title` unless a longer one reads better |
| `diplotypes.phenotype` | card heading when called; the name of each possible result | a result a person could say out loud: *Blood group AB*, *RhD negative* |
| `diplotypes.conclusion` / `variants.conclusion` | the explanation under the result | layer 1 + layer 2, rules below |
| `README.md` | catalog page, and the professional's reference | layer 3 in full: sites, alleles, sources, what is not covered, how the module was made |
| `weighting.note` | *Modules in this report* table (professional) | technical is fine here |
| `studies.csv` | study table under a variant row (professional) | exact, verbatim, sourced |

## Writing a conclusion

A conclusion is **two to six full sentences, roughly 40 to 130 words**: shorter for a simple result,
longer when there is a *why* worth telling. Aim to leave **both audiences satisfied and a little
curious**: the lay reader should understand the result and learn something, the professional should
find nothing wrong with it. In this order:

1. **The result in plain words, about the reader.** Start with what they have, in the second person.
   *"You have blood group AB."* Not *"A/B diplotype"*, not *"GA variant is associated with…"*.
2. **What it means.** One or two sentences on what this is and what it does, in everyday terms.
3. **How common it is**, as a natural frequency: *"about 4 in 100 people in Europe"*. Never a bare
   percentage without a reference group, never an odds ratio. Frequencies differ a lot between
   ancestries, so name the group, or give a range across populations. When no figure can be sourced,
   say *common*, *uncommon* or *rare* rather than inventing a number.
4. **A practical note, when the evidence supports one** (see below). When the implication is clear
   and well established, say it: blood group O is the universal red-cell donor, AB the universal
   recipient. Do not leave the useful sentence out because it sounds too practical.
5. **Something interesting, when it is true and sourced.** The *why* a curious person never learned:
   blood groups are about the immune system (you carry antibodies against the markers you lack, which
   is why mismatched blood is attacked); the common O allele is an A allele broken by one missing
   letter. One sentence, accurate, no trivia for its own sake.
6. **How to check it yourself**, when there is a way: a blood donor card, a routine test, a trait you
   can observe. Teaching modules especially should say this.
7. **How sure, and what it cannot tell.** Calibrated words, and the limit that matters most.

Before and after, from a real row:

> **Before:** GA variant is associated with increased risk of hyperhomocysteinemia and thrombophilia.
>
> **After:** You carry one copy of a common MTHFR variant, which slightly lowers how well your body
> processes folate. On its own it has little effect: about 4 in 10 people in Europe carry one copy,
> and most never have a problem. Studies link it to a small rise in homocysteine (an amino acid in
> the blood) and, weakly, to blood clots. It is not a reason to take supplements unless a doctor has
> measured your homocysteine and found it high.

> **Before (card):** `RHCE` · *Ambiguous* · Ce / ce — C+ c+ E- e+ · Ce / cE — C+ c+ E+ e+ …
>
> **After (card):** *More than one possible result* · RHCE gene. "Your DNA file fits more than one of
> the results below… **Rh markers C+ c+ E− e+**: Your red cells carry the Rh markers C, c and e but
> not E…"

### Rules

- **Full sentences.** No telegraphic fragments, no noun stacks, no arrows or slashes standing in for
  words. If it would sound odd read aloud to a friend, rewrite it. Simple does not mean short: *"Two ε3
  alleles: the reference genotype most risk estimates are expressed relative to."* is short and
  unreadable. Use as many plain sentences as the idea needs: what the reader has, what the gene does,
  how common it is, what it means in practice, and the main limit.
- **Say "you".** The reader is a person, not a sample.
- **Explain a necessary term the first time**, in the same sentence: *"homocysteine, an amino acid in
  the blood"*. If a term is not necessary, drop it.
- **One idea per sentence.** Short sentences beat semicolons.
- **Name the direction plainly**: *raises*, *lowers*, *no effect known*. Not *"associated with"* on
  its own, which tells a reader nothing about which way or how much.
- **Put size before scariness.** *"A small increase"* before the disease name, never a disease name
  with no size at all.
- **Calibrate certainty** with a fixed ladder, so words mean the same thing across modules:
  - *well established*: replicated, large studies or a clinical guideline;
  - *likely*: consistent evidence, not yet definitive;
  - *early evidence*: one or few studies, small or unreplicated;
  - *not known*: say so, and do not guess a direction.
- **Not destiny.** For any risk result, say that most people with it do not develop the condition when
  that is true, and name the other factors that matter more when they do.
- **No fear, no hype.** No *"alarming"*, *"dangerous"*, *"superhuman"*, *"elite"*. Protective results
  are stated as calmly as risk ones.

### Practical notes: allowed, bounded

Practical context helps people and is allowed **when the evidence is solid**:

- **Allowed:** everyday context and when to act. *"If you donate blood, the blood service tests your
  group anyway."* *"People with this result often find that coffee late in the day keeps them
  awake."* *"If you are pregnant, your midwife will check your Rh status with a blood test."*
- **Always name who decides** anything medical: a doctor, pharmacist, midwife, blood service.
- **Never** tell a reader to start, stop or change a medicine, a supplement, a diet or a treatment,
  and never suggest a DNA result replaces a lab test. Drug-response modules say *"tell your doctor or
  pharmacist about this result before starting X"*, not *"avoid X"*.
- **No practical note is better than a weak one.** If the tip rests on one small study, leave it out.

### Special cases the report handles for you

The template already writes these sentences; a module should not repeat them, but its conclusions
must not contradict them.

- **Read as reference** (a position the file did not record, inferred from nearby coverage): the
  report labels it *assumed reference* and explains the doubt under More details.
- **Cannot be read from this file**: the report says so and lists the possible results under *What
  the possible results mean*. So write each possible result's conclusion so it makes sense to someone
  who might have it, not only to someone who does.
- **More than one possible result**: the report lists each one with its conclusion. Two allele pairs
  giving the same result are shown once, so give them **identical** `phenotype` labels and identical
  conclusions.

## Asking the module author, sparingly

When an agent writes a module with somebody, the person usually knows what they care about: which
result they want explained well, who they are writing for, whether the practical side or the
biology matters more to them. **Ask only when it is genuinely unclear and it changes the text**, at
most one or two questions, once, near the start of writing conclusions. Good reasons to ask:

- the module could lead with two different angles (*"should the caffeine results focus on sleep or
  on sport performance?"*);
- a practical note is borderline and the author may know their audience (*"is this module for
  people planning a pregnancy, or general curiosity?"*);
- a technical term has no plain equivalent and the author may prefer one framing.

Do not ask about anything the sources settle, about wording you can simply get right, or for
approval of each conclusion. Offer a sensible default in the question, so a one-word answer works.

## Phenotype labels

A `phenotype` label is layer 1 on its own, so it must stand alone as a sentence fragment a person
would say: *Blood group O*, *RhD negative*, *Fast caffeine metabolism*, *Non-secretor*. Short (up to
about six words). Standard notation is fine **after** a plain anchor: *Rh markers C+ c+ E− e+*, not
*C+ c+ E- e+* alone. Never a code (`B/O1`, `*1/*2`, `PAV/AVI`); those belong in layer 3.

## Phenotype modules: patterns that recur

A phenotype module (haplotypes + diplotypes) lists **several possible results** whenever a file cannot
settle one, so its text is read in ways a single-variant row never is. The template handles the
mechanics (it groups allele pairs by label, sorts firm results first, prints sentences that every
listed result shares only once, and drops the per-result "cannot confirm" tag on a card that already
says the file cannot read it). The author's side:

- **Put the distinct sentence first, the shared background after, and word the shared part
  identically** across sibling results. The report factors out only sentences that match exactly;
  "Rh markers are proteins…" in one row and "The Rh markers are proteins…" in another prints twice.
- **Every result must read correctly as a possibility.** When the file cannot decide, a reader sees
  all of them, most of which are not theirs. Avoid sentences that are only true if this is the
  reader's result *and* would alarm someone for whom it is not.
- **Make the label carry the topic when the gene symbol does not.** A card is headed by the result
  and tagged with the gene symbol; *RhD negative* explains itself, *C+ c+ E- e+* does not, so it
  becomes *Rh markers C+ c+ E- e+*.
- **A gene the file cannot read still earns its card**: the possible results are shown under *What
  the possible results mean*, so each one should tell the reader what it would mean and what to ask a
  lab about.

## Independent review before publishing

The writer is the worst judge of both readability and accuracy, because they know what they meant.
Before a module is published, and again whenever its conclusions change substantially, run **two
reviewers as separate agents, with deliberately different inputs**. Review the **rendered report**
from a trial install on real genomes where you can (repetition, ordering and missing context only
show up rendered), plus the full list of result texts, since three genomes never show every result.

**1. The lay reader.** Input: only the plain part of the rendered reports (More details folds
hidden) and every result text. No sources, no web, no expertise. Brief: play an adult with no
science training who remembers school biology vaguely. Output:

- each person's result restated in their own words (**the pass test**: if a restatement is wrong,
  the text is wrong, however accurate it is);
- every word or sentence they would not understand or would misread, quoted, with a plainer wording;
- anything repetitive, contradictory, alarming or machine-sounding, quoted;
- what they would want to know next;
- a verdict and the single most important fix.

**2. The scientific reviewer.** Input: the rendered reports including the folds, the spec tables,
`README.md`, and literature access (PMIDs only from a search result whose title was read). Brief: a
specialist in the module's field checking whether any simplification became **wrong or misleading**,
not whether it is simple. Output:

- errors, with a corrected sentence just as plain;
- misleading or overstated claims, corrected;
- missing caveats that matter for safety or correct understanding (not expert-only caveats);
- mapping errors in the tables (an allele pair given the wrong result);
- practical notes that cross into medical advice;
- claims that could not be verified;
- a verdict.

**3. A family check, when related genomes are available.** Inheritance is ground truth that needs no
outside source: a child carries one allele from each parent, so the calls on a family must fit
together at every site and for every combined result. `scripts/family_check.py <module> --mother …
--father … --child …` checks both levels and reports a site or gene that was not readable in
everyone as *unchecked*, never as a pass. A violation means a wrong call, a sample swap or
non-paternity. It is the only one of the three checks that can catch a wrong **call** rather than
wrong **text**, but note what it cannot catch: an allele definition that is wrong in the same way for
everyone (the rs609320 E/e swap this module first shipped with) is still perfectly Mendelian.

**Reconcile as the author.** Fix every error. Take readability fixes that lose no accuracy. When the
two reviewers pull in opposite directions, keep the accurate claim and find a plainer way to say it;
if that fails, that is one of the one or two questions worth asking the module author. Then record
the review: a line in `README.md` (date, what was checked, what changed) and an `authorship:` entry
with `role: reviewed` and `kind: [ai, agent]`. An AI review is recorded as exactly that, never as a
human one.

**Give every common name.** When a result is known by different names in different regions or
traditions, the label carries both and the conclusion says so once: *Blood group B (III)*, "called
group III in some countries". Our readers are international; a result they cannot recognise in their
own nomenclature reads as a wrong result.

## Plain words for common terms

| Instead of | Write |
|---|---|
| genotype | your DNA letters at this position; your version |
| allele | version (of a gene), DNA letter |
| heterozygous / het | one copy, inherited from one parent |
| homozygous / hom | two copies, one from each parent |
| variant, SNP, polymorphism | a spot where people's DNA commonly differs |
| haplotype | a version of a gene |
| diplotype | the pair of gene versions you carry, one from each parent |
| phenotype | trait, result |
| VCF, callset | your DNA file |
| reference allele | the reference version (the one in the standard human genome) |
| phase, unphased | which DNA letters you inherited together from the same parent |
| risk allele | the version linked to higher risk |
| odds ratio, relative risk | a natural frequency: "about 3 in 100 instead of 2 in 100" |
| penetrance | not everyone with this version develops the condition |
| pathogenic | known to cause disease |
| VUS | effect not yet known |
| not assessable | cannot be read from this DNA file |

## For report and template developers

- **Status words are everyday words.** *Result*, *Partly known*, *Not readable from this file*,
  *Unusual combination*. The caller's codes (`called`, `ambiguous`, …) appear only in the professional
  fold.
- **Every card leads with layer 1, then layer 2, then the fold.** The module's `conclusion` must be
  visible without a click; the professional material is one click away, never absent.
- **No developer output outside the fold.** Build warnings, compiler codes, file paths and digests
  never sit in the plain part of the page. In the fold, label them for who they are for (*"Module build
  warnings (for the module's authors)"*).
- **Every result gets the AI-assistant buttons**, per-variant rows and phenotype cards alike, as
  bare icons: no label or note beside them, which would dwarf a 28 px icon. The privacy notice (the
  prompt carries the person's DNA letters and is sent only on click) is in each button's tooltip and
  `aria-label` (`_AI_PRIVACY_NOTE`), and explained in full at the bottom. A phenotype prompt carries the result or the possibilities, the module's explanation and
  every defining position as read, and asks for the same layered explanation this guide asks of
  modules (`_build_phenotype_ai_prompt` in `report_logic.py`).
- **Preamble goes to the bottom.** The page opens with the title, the description and the results.
  General explanations, table help and the interpretation notice live in *How to read this report*
  at the end, and the contents list appears only when a report has more than one section.
- **Only explain controls the page has.** Help text for tables, *Open all* and the AI buttons appears
  only when those elements are on the page.
- **Name people, not files**, when a label is known: *Livia Zaharia*, not `SIMHIFQTILQ.hard-filtered`.
  *(Not done yet: the report header still shows the sample file name.)*
- **One partial per module kind.** The phenotype section is `phenotype_section.html.j2`, with its
  own vocabulary and help text; the per-variant and drug sections still live in
  `longevity_report.html.j2` and should move to their own partials next. Shared page parts (header,
  notice, contents, reproducibility, credits) stay in the base. A kind's help text lives in its
  partial, so a page shows only help for what is on it.
- The phenotype card follows this now (`phenotype_section.html.j2`; `phenotype_readings`,
  `factor_shared_sentences`, `phenotype_topic`, `phenotype_rules` and `readme_section` in
  `report_logic.py`). **The per-variant tables do not yet.** They still lead
  with rsID / Ref / Weight columns and hide the conclusion behind **+**. Bringing them in line (a
  plain answer column first, technical columns folded) is the next template change, and it has to
  respect the JavaScript constraints listed in `AGENTS.md` under *The report's side of the contract*.

## Checklist before a module is published

- [ ] Every `phenotype` label reads as something a person would say, with no codes, and gives every common regional name.
- [ ] Every conclusion starts with "You…" (or an equivalent plain statement of the result).
- [ ] Clear practical implications are stated; an interesting, sourced *why* is included where one exists; a way to check it yourself is named where one exists.
- [ ] No rsID, HGVS, allele code, coordinate, p-value or odds ratio in any label or conclusion.
- [ ] Every risk statement has a size and a frequency, and says it is not destiny where that is true.
- [ ] Every practical note is backed by solid evidence and names who decides anything medical.
- [ ] No instruction to change a medicine, supplement, diet or treatment.
- [ ] Allele pairs with the same result share an identical label and conclusion.
- [ ] `README.md` carries the full professional layer: sites, alleles, sources, limits, origin.
- [ ] A combination module has a plain `## How this works` section in `README.md`, and authors no weights.
- [ ] No disclaimer, warning or privacy text sits above a result; a result's own caveat is its last sentence.
- [ ] Read three conclusions aloud. If any sounds like a database row, rewrite it.
- [ ] The two independent reviews (lay reader, scientific reviewer) ran on the rendered report, their findings are reconciled, and the review is recorded in `README.md` and `authorship:`.
