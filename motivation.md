I have always been disappointed with the scarcity of maps in history books. Often, I have found myself re-reading a chapter along with an atlas (or online maps) by my side.

I decided to try using LLMs for map generation. I gave 5 pages of text (describing a particular episode) from history book Google Gemini 3 (Thinking) and asked it to produce a map. To my pleasant surprise, it produced a <a href="https://home.chetanv.net/history_cartopy/gemini-attempt1.jpg">very pretty map</a> - which had most of the story-line. But look closer and one sees the problems. For example - the same river is labelled as Godavari/Krishna/Karnatak, the framed title appears twice, etc. After asking for some corrections and changes, the map produced looked <a href="https://home.chetanv.net/history_cartopy/gemini-attempt2.jpg">very different and wrong</a>.

Realizing that this one-shot text to map generation (and subsequent tweaking) is not possible with current LLMs, I settled upon having an intermediate YAML description of the map - and a program to convert the YAML to a PNG map. Digesting a bunch of text and creating a well-specified YAML is a task suited for LLMs.

Making the map non-cluttered and "beautiful" is where the challenge lies. I made a beginning with a Python based script - which quickly grew into a mid-sized project. Google Gemini and Claude Code were used extensively. And the generated output maps are "not so bad".

Check https://github.com/chetanvaity/history_cartopy/
