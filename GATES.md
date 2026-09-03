# Gates: close archive quality gaps

OWNS: archive/**, scripts/**, docs/study-design.md, CHANGELOG.md, AGENTS.md

- [x] G1: automated archive consistency check exists and passes on the live archive
  CHECK: python3 scripts/check_archive.py
  EXPECT: archive check passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=47b92ab244b929d47ac880d23c3a5f401051a39f3a29130e9db03e980091556c; output-bytes=21

- [x] G2: negative control - the checker fails on a deliberately broken fixture
  CHECK: python3 scripts/check_archive.py --selftest
  EXPECT: selftest passed
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=13b26c4713e9a6044bd5a632561cfe1e24511312339245396dbb7d5b90edb838; output-bytes=16

- [x] G3: no archive entry carries a placeholder author field
  CHECK: python3 scripts/check_archive.py --report
  EXPECT: placeholder_authors: 0
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=ede975678092c39ef0c6c687cc69834cbb6f2da7fd612a08bb4d2d48391b4717; output-bytes=73

- [x] G4: full-text verification coverage at least doubled (>= 20 of 51 entries)
  CHECK: python3 scripts/check_archive.py --report
  EXPECT: /ft_verified: (2\d|[3-9]\d)\/51/
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=ede975678092c39ef0c6c687cc69834cbb6f2da7fd612a08bb4d2d48391b4717; output-bytes=73

- [x] G5: INDEX [FT] rows equal entries marked verified from full text
  CHECK: python3 scripts/check_archive.py --report
  EXPECT: ft_index_mismatch: 0
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=ede975678092c39ef0c6c687cc69834cbb6f2da7fd612a08bb4d2d48391b4717; output-bytes=73

- [x] G6: study design red-teamed; findings recorded in the document
  CHECK: python3 -c "import sys; t=open('docs/study-design.md').read(); sys.exit(0 if '## Red-team findings' in t and t.count('**Attack**') >= 4 else 1)" && echo redteam-section-present
  EXPECT: redteam-section-present
  EVIDENCE: exit=0; shell=/bin/sh; cwd=<repo>; path=4f1febc988dd/17 entries; EXPECT=matched; output-sha256=5c5e1956e44bbc3c89e99472d06fed2cccff3066994fedf29ba3cacd81b5d2a1; output-bytes=24

- [ ] G7: study executed with real models and human baseline
  EVIDENCE: abandoned, see ABANDON line

ABANDON: G7 requires a lab (open-model inference node, IRB approval, 120 human participants, 12 weeks); not executable by an agent inside this repository. Protocol handed off in docs/study-design.md v0.2.
