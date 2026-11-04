s = open("gen_s14.py").read()
rep = [
 ('REG = pd.read_csv("S14_longevitymap_register.csv", dtype=str).fillna("")',
  'REG = pd.read_csv("S14_longevitymap_register.csv", dtype=str).fillna("")\nREG = REG[~((REG.origin == "paper verification") & (((REG.rsid == "rs28940577") & REG.category.str.startswith("E9")) | ((REG.rsid == "rs28940579") & (REG.pmid == "17048073"))))]\nREG.to_csv("S14_longevitymap_register.csv", index=False)'),
 ("model without individual replication. HAGR's conclusion text describes this correctly at model level, but the per-SNP\n  flag is what the module used. These 279 rows are 52% of the module's rsIDs.",
  "model without individual replication. HAGR's conclusion text describes this correctly at model level, but the per-SNP\n  flag is what the module used. These 279 SNPs are 53% of the module's rsIDs."),
 ("   status, the genes it overlaps, and, for the 26 named variants the import or curation translated into rsIDs, the\n   protein change on the canonical transcript.",
  "   status, the genes it overlaps, and, for the coding variants that the import or the curation translated from a name\n   into an rsID, the protein change on the canonical transcript."),
 ("""database; 96 of these replace a named variant with an rsID. The 26 translations checked against Ensembl protein
annotation are correct once legacy numbering is allowed for (for example CETP I405V = p.Val422Ile; AGT M235T =
p.Met259Thr), with two exceptions. Every HAGR "E2/E3/E4" record""",
  """database. 96 replace a named variant with an rsID. 14 replace a HAGR rsID that no longer resolves in Ensembl with a
current one, mostly dbSNP merges (for example IL6R rs8192284 → rs2228145, VDR rs10735810 → rs2228570); two of the old
identifiers, rs28940479 and rs37926683, look like typing errors. 8 rare-variant identifiers were left empty. Of the
named-variant translations made by the import or the curation, the 15 coding ones were checked against Ensembl's protein
annotation: 14 are correct once legacy numbering is allowed for (for example CETP I405V = p.Val422Ile, AGT M235T =
p.Met259Thr) and one, MEFV M694V, is not (below). Two import mappings are wrong. Every HAGR "E2/E3/E4" record"""),
 ("- **Transcription.** Entry 1887 gives rs28940479 for MEFV; the variant studied is rs28940579 (corrected by the\n  Generation I import).",
  "- **Transcription and retired identifiers.** Entry 1887 gives rs28940479 for MEFV, where the variant studied is\n  rs28940579, and entry 2086 gives rs37926683 for rs3792683. Twelve further records use rsIDs since merged in dbSNP. The\n  Generation I import corrected all fourteen."),
]
for a, b in rep:
    assert a in s, a[:60]
    s = s.replace(a, b)
open("gen_s14.py", "w").write(s)
