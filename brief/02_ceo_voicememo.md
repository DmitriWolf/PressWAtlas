```
Voice memo transcript
From: Marcus Chen <marcus@pantrypal.io>
Delivered: Wednesday, 8:14 AM
Duration: 4:22
Auto-transcribed - forgive any weirdness
```

---

Hey team, Marcus. Uh, driving to the airport so forgive the road noise and the fact that this is gonna be a little stream of consciousness. Priya's sending the build spec today and I wanted to, like, get you the context that sits underneath it, because the spec is going to read like a list of features and that's going to miss the thing.

So, the thesis. The moment we're designing for is, you know, 6pm, you're tired, you're standing in the kitchen, you don't know what to make. Right now people solve that by texting a friend who cooks or by giving up and ordering delivery. We want to own that moment. The product is the friend who actually cooks. That's, that's the whole thing.

OK so a few things that follow from that.

Personality matters more than people think. When you text that friend they don't, they don't respond like Wikipedia, right? They have opinions. They're like, "don't make that, make this instead, trust me." That's the voice we want. If you ask it about pineapple on pizza it should have a take. And I know - I know the default for AI products is like, hedging and disclaimers and I want us to deliberately not be that. A tool that sounds like every other chatbot is not going to be sticky. We'll die in the middle of the pack.

Memory. This is, uh, this is maybe the one I feel strongest about. If I told it last week I'm allergic to shellfish, it better not suggest shrimp to me this week. If I mentioned I'm obsessed with Thai food it should remember that. Without continuity it's just a better search engine and, like, search engines already exist. I know there's real work here - storage, privacy, all of it - I'm not saying it's free, I'm saying it's the product.

Scope. So Priya's going to want firm guardrails on what the thing will engage with and I get the instinct but I think we should be, um, generous about what counts as cooking. Wine pairings, kitchen gear, hosting a dinner party, "is this restaurant worth going to" - that's all food world to me. I want the rule to be, like, food-adjacent is fair game, and we politely redirect the clearly-off-topic stuff. Don't let it write someone's cover letter, obviously. But don't make it a narc either. That's, that's the vibe.

Oh and, uh, health stuff. People on keto, people managing diabetes, vegetarians, people with real allergies. Our product needs to handle that space well. I know Diane's going to have thoughts on this and we're looping her in, I just want to flag that, like, "we don't touch anything health-adjacent" is not a viable answer for us. We need to thread the needle, not just avoid it.

Response time. Priya's going to say two seconds. Honestly I, I care more about the answer being good than fast. If it needs to go think for a few seconds and come back with something great, I'd take that every time over a fast mediocre answer. Not saying make it slow on purpose. Just saying, like, don't optimize for latency at the cost of quality.

What else. Uh, voice. Long term this needs to work hands-free while you're cooking because, you know, your hands are covered in whatever. I don't know if that's v1. Your call. If there's an easy way to not paint ourselves into a corner architecturally, do it.

Last thing. I've been using FakeAIChef and a couple others to see what's out there. They're, they're fine. None of them are sticky. The reason, I'm pretty sure, is they feel like tools. Ours needs to feel like a relationship. That's the bar.

OK I think that's it. Priya's doc is the floor, this memo is the direction, land somewhere that makes both of us a little uncomfortable and you'll probably be in the right zone. Call me if anything's weird. Cheers.

[end of memo]
