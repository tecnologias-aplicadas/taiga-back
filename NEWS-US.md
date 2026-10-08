# What's new in this Taiga fork (back-end)

This repository is the back-end of a fork of [Taiga 6.8](https://taiga.io), maintained by Centro de Tecnologias Aplicadas - Itaipu Parquetec, a technology center in Brazil. The original code belongs to [Kaleidos and the taigaio project](https://github.com/taigaio); the fork remains under the AGPL-3 license, with the credits preserved.

The full description of every feature, with the reason behind each one, is in the front-end news document: [NEWS-US.md in taiga-front](https://github.com/ta-iot/taiga-front/blob/main/NEWS-US.md). Here is only what the server implements, since the rule of this fork is that the server decides and the interface only reflects it.

## What the back-end implements

- **Partial progress per task status**, an integer from 0 to 100 or empty; closed counts 100 and open set to 100 becomes 99.
- **Done and in-progress percentages** computed and recomputed in cascade from task to story to epic; not editable through the API.
- **Epic start, planned end and completion dates**, refusing an end before the start and filling the completion date on close.
- **Epic schedule**: schedulable flag and impact per epic, plus a management command that stores the monthly snapshot without rewriting past months.
- **Relations between cards** with fixed types, one active relation per combination, history on both cards, permission per role and soft deletion.
- **Blocking by relation**: a blocked card does not move to a closed status and is not deleted until the relation is resolved.
- **Emoji reactions on comments**, one per emoji per project member, removed by their author.
- **Project start, planned end and end dates**, with order validation.
- **Restricted project creation** to admins and superusers, private project by default.
- **Two-path authentication**: corporate account through the institutional directory (LDAP), external account with a local credential, reCAPTCHA on both when enabled; a corporate account cannot change e-mail or access credential.
- **Home news carousel**: public read API for active slides and superuser-only writes, with image, size and text-limit validation; starts empty in any installation.
- **Translations** of server texts in pt-BR, en and es.

For the behavior of each item and the note on corporate access, see the taiga-front NEWS.
