# Nieuwe chat overdracht — EnergieProject na v10.4.5

Basis vóór test: v10.4.2-productie met permanente QNAP-cronwatcher. v10.4.3 en v10.4.4 waren gecontroleerde mislukte releaseproeven en staan in `failed`.

v10.4.5 verhelpt de twee QNAP-installerbeperkingen die tijdens die proeven zijn vastgesteld: Git is optioneel en installatie/rollback bewaren geen metadata/timestamps op de projectshare. De installer voert vóór worktree-vervanging een QNAP-schrijf/kopie/verwijder-preflight uit.

Voor v10.4.5 is één eenmalige bootstrap nodig omdat de actieve oudere installer zichzelf niet met de nieuwe installer uit een ZIP kan vervangen. Na succesvolle v10.4.5 moet de normale werkwijze weer zijn: alleen ZIP in `incoming`.

Failed releases pas opruimen nadat v10.4.5 en minstens één daaropvolgende ZIP-only release succesvol zijn bewezen.
