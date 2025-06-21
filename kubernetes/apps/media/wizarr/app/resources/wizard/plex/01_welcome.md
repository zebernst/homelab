---
title: "Welcome to {{ server_name }}!"
---

# {{ _("Welcome to") }} {{ server_name }}!

## ℹ️ {{ _("So, what is Plex?") }}

{{ _( "Plex lets me share my TV and film libraries with my friends and family. "
      "If you’re here, that means you've been granted access to my Plex server") }} **{{ server_name }}**.

## 🍿 {{ _("How do I watch?") }}

{{ _("Install the Plex app on your phone, tablet, computer or smart TV, sign in, and hit play. That’s it!") }}

{{ _("You can also watch in your browser at") }} [{{ server_url | replace("https://", "") }}]({{ server_url }}){:target=_blank}
