# Changelog

## 32.4.54 — generation-fenced release transition

- Eén duurzame release-transition is nu de enige planner voor technische release-closure; oude 32.4-projecties zijn read-only.
- Release ownership is expliciet en legacy release-taken worden hash-gebonden gereconcilieerd zonder GLOBAL taken op tekst te raken.
- Hold, mode, command queue en protected executors zijn generation/phase/revision/ticket-afgeschermd; stale approvals en normale mutaties falen gesloten.
- 32.4.53→32.4.54 gebruikt een fail-closed legacy hold+atomic bootstrap; volgende releases schrijven TRANSITION_PREPARED vóór de swap.
- Crash/restart recovery herhaalt onbekende side effects niet blind; onzekere executorstatus blokkeert.
- Handover projecteert de transition als centrale releasewaarheid en startup registreert echte monotone fase-timings.
- Codex adversarial review hardening: alleen directe fase-opvolgers zijn toegestaan; executorresultaten vereisen exact phase/release_owner/revision-ticket.
- Voltooide generations rollen lease-beschermd naar historie zodat 32.4.55 en later een nieuwe current generation kunnen starten.
- Transition-lock bootstrap is lstat/O_NOFOLLOW fail-closed; dangling symlinks mogen geen doelbestand creëren.
- Mode restore is een ticketed executor met readback en herstelt previous_base_mode; GUI hold-validatie muteert niet tijdens een actieve transition.
- Target identity: EnergieProject 32.4.54 / Projectmanager 2.0.0-rc41.
