# SPRINT 4 — Simulateur de pitch : « s'exercer et perdre la peur » (Semaines 7-8) · backend

> 🎯 **Objectif :** l'IA joue l'investisseur, pose les vraies questions, donne un feedback sur le
> Radar ; le porteur rejoue à volonté et voit ses progrès. Pièce maîtresse de la transformation.
> 🧪 **Démo :** une session de pitch complète → feedback Radar → rejeu → progression visible.

**Capacité backend : 19 pts** — *sprint volontairement léger : story la plus novatrice/risquée
(qualité conversationnelle), on garde de la marge pour itérer prompts & UX.*

Détail : [BACKLOG.md](../docs/BACKLOG.md#sprint-4--simulateur-de-pitch--sexercer-et-perdre-la-peur).

## Board

### ⬜ To Do
- **IDX-PITCHSIM-01** Moteur de session conversationnelle `[8]` — `practice_sessions`, `POST /pitch-sim/start`, `/{id}/turn` ; prompt versionné, ton exigeant mais bienveillant.
- **IDX-PITCHSIM-02** Feedback structuré sur le Radar `[5]` — 6 axes (réutilise `scoring`) + forts/à-travailler ; `pitch_feedback`.
- **IDX-PITCHSIM-03** Rejeu & historique `[3]` — `GET /pitch-sim/sessions`.
- **IDX-PITCHSIM-04** Progression (boussole avant/après) `[3]` — *front-dominant* ; backend = série temporelle des scores.

## DoD du sprint
- [ ] Session conversationnelle persistée tour par tour ; rejeu illimité.
- [ ] Feedback mappé sur les **6 axes** du Radar (cohérent avec diagnostic).
- [ ] Prompt **versionné** ; coût LLM maîtrisé (provider bon marché).
- [ ] Événements d'instrumentation émis (pitch joué, score) — alimente INSTRUM.
