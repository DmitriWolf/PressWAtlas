```
From: Priya Natarajan <priya@pantrypal.io>
To: [Consultant]
Cc: Marcus Chen <marcus@pantrypal.io>
Subject: PantryPal v1 - scope for the first build
Date: Tuesday, 10:47 AM
```

Hi team,

Thanks again for jumping on this. Marcus (our CEO) is excited and I want to make sure we give you enough to actually build against. I've tried to consolidate what we've been discussing internally into something concrete.

**The product, in one sentence:** an AI cooking assistant users talk to when they're trying to figure out what to cook.

**What v1 needs to do:**

1. Answer general cooking questions ("how do I know when chicken is done," "what can I substitute for buttermilk")
2. Suggest recipes based on what the user wants ("something spicy and fast," "dinner for four")
3. Help them figure out what they can make with the ingredients they have
4. Stay in its lane. This is a cooking assistant. It should refuse to answer things that aren't about cooking. We want users to know what it's for.

**Non-negotiables from our side:**

- Response time under 2 seconds. Users are impatient and we've seen drop-off on competitor products with slow responses.
- It has to check whether the user can actually make what it suggests. Our early testers HATE being told to make something that requires equipment they don't have.
- Needs to feel like a real product, not a demo. Marcus is adamant about this. Clean chat UI, conversation flow feels natural, no weird AI tells.

**On the "what does the user have" question:**

This is the thing I'm least sure about. Originally we assumed every user has the same basic starter kit (spatula, frying pan, knife, a couple pots, the obvious stuff) and we'd just check recipes against that list. Jordan from CX can tell you how that's been going - not great. Our users don't all own the same things. Some of them have way more, some have way less.

I don't want to ship v1 with a fixed assumed list because it's going to be wrong for most of our users on day one. Figure out what makes sense here and tell us what you built and why. This is exactly the kind of call I'd rather have you make than dictate.

**Stack guidance:**

We don't care what you use on the backend as long as it's Python-based so our team can maintain it. For the frontend, keep it simple - we'll probably rebuild it anyway when we have a design system.

**Unit economics:**

I know it's early but please keep an eye on per-query cost. We can't have a product where every conversation costs us a dollar. If we have to pick between a faster model and a cheaper one for the simple stuff and a smarter one for hard queries, I'd rather be clever about routing than just defaulting to the expensive option.

**Timeline:**

Marcus will send you his broader vision separately (he's doing a voice memo because he's driving). Treat his notes as directional - the list above is what we're actually committing to for v1. Please push back if any of this is unrealistic.

Thanks,
Priya
Head of Product, PantryPal
