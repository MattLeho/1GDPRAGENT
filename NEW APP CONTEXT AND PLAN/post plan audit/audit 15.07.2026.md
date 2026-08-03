im reviewing the app now. I can see that, unfortunately, there is lots to do still so we need to re audit all of the 6 plans as I dont believe they have been fully implemented. Here is a list of errors I found from a quick pass:

SETTINGS:

Profile and Identity page:

When I change the username, it doesnt change it to match in the top right user profile image. When I save, nothing happens.

Image 1: Connectors page

I was expecting a button for quickly connecting to emails via oauth and to the browser the frontend is working on to pull history and sync it. But the "Source type" connector doesnt even work and when I go on it says im in an "invalid Session".

Would be cool to have not just STMP and IMAP monitoring but also some easy oauth connectors for outlook and gmail.

PROCESSING AND MODELS:

There are lots of settings here. Firstly, when I try to multi task, like now where im trying to look at the app and write all the problems for you, the UI breaks and is squashed (See image 2); so you need to fix the UI so it works in any aspect ratio, and that stands for the whole app.

Secondly, the model selector is a type box, it would be more useful if the system can auto detect models that are available and recommended from the task based on the provider, so for example if I click local via ollama, or NVIDIA, it scans the system to see which models are installed, or if I select openrouter, it pulls the available models and suggests them in a dropdown rather than me having to type the models in, but keep an "Other" option where I can type my own model just in case.

The suggestions need to be smart. We dont want to use Gemini 3.1 pro for Topic Labelling, a small model like Gemma would be good enough for that- so bare that in mind, im not sure if there are variables we can set when calling the model APIs to filter and only get models that fit certain parameters, like specifically an SLM for a given task, you know?

its good that the main provider is before the model selection, and the fallback is after but I cant select a fallback model so what if my local model is parakeet, but then my fallback is gemini? There is no way of setting that because there is only one space to select my model, a box for the fallback model doesnt exist, only the fallback provider box is there. "NVidia Generation" is unclear in what it means- is that NVidia NIM, like the cloud provider, or local NVIDIA inference?

Also it would be nice when I click "Health", if, for example, the parakeet model isnt installed on my system, it would be nice to get a pop up where i can click a button and the app sets it up for me automatically- like it checks my system to see if its capable of running the model, if not it suggests using a private cloud, but if it is, it installs the model and sets everything up so we can use it.

then we have the visual models- what does "local visual model" even mean?? What is that running on? Ollama? But we have ollama as a seperate provider option so what does local visual model mean? Where is it running?

DATA GRAPH:

I have Neo4j live and running on my system within the docker container. Ive logged into neo4j on its own frontend in the tab, but on the "Data Graph" page, im getting an error: Failed to load graph- Graph API returned 401. We need to fix this, i shouldnt even have to log into Neo4j on the other tab, it should automatically connect through the credentials in env. And i should be able to edit and adjust the credentials in my settings page but right now its missing from the settings page. (Image 4)

I also asked for the graph page to have a slider where i could slide through the dates or, if I want, have 2 draggable dots on the slider so I can select a specific period- so 2 types of sliders one for a date (which would include "now", and one for a period of time. Compare, controller profile, capabilities, linkability, purpose and access are all fine otherwise but dates and time needs to be on a slider, not a button.

"Through time" could be a pre-processed video of the graph that plays through it and animates the nodes coming in, growing and shrinking and disappearing to visualise how interests changed and how the graph evolved over time.

The left sidebar takes up a lot of the screen and I would like it to be collapsible.

Im getting 2 errors when I try to switch page:

error 1:

## Error Type

Console Error

## Error Message

Database query failed: column "updated_at" does not exist

at Object.query (lib/db.ts:45:21)

at safeQuery (lib/db.ts:82:24)

at getEnhancedDashboardStats (lib/actions/dashboard.ts:190:29)

at Function.all (<anonymous>:1:21)

at DashboardHome (app/dashboard/home/page.tsx:26:51)

at DashboardHome (<anonymous>:null:null)

## Code Frame

43 | // Log the error but re-throw for caller to handle

44 | const message = error instanceof Error ? error.message : 'Unknown database err...

> 45 | console.error(`Database query failed: ${message}`);

| ^

46 | console.error('Query:', text.substring(0, 200));

47 | throw error;

48 | }

Next.js version: 16.2.7 (Webpack)

Error 2:

## Error Type

Console Error

## Error Message

Query: "\n SELECT \n COALESCE(AVG(\n EXTRACT(DAY FROM (\n CASE WHEN status = 'completed' THEN updated_at ELSE NULL END - created_at\n ))\n "

at Object.query (lib/db.ts:46:21)

at safeQuery (lib/db.ts:82:24)

at getEnhancedDashboardStats (lib/actions/dashboard.ts:190:29)

at Function.all (<anonymous>:1:21)

at DashboardHome (app/dashboard/home/page.tsx:26:51)

at DashboardHome (<anonymous>:null:null)

## Code Frame

44 | const message = error instanceof Error ? error.message : 'Unknown database err...

45 | console.error(`Database query failed: ${message}`);

> 46 | console.error('Query:', text.substring(0, 200));

| ^

47 | throw error;

48 | }

49 | },

Next.js version: 16.2.7 (Webpack)

Back to the squishy UI issue, you can see in image 3 that it persists on the homepage, even though we have perfectly enough space for it to fit in this space. This needs to be fixed.

For some reason the privacy policy scan is still failing, is this because ive not configured any models yet in the settings? Either way, it doens't work.

For the AI chat within the requests page, the error message states "I encountered an error while processing your request: No Google AI API key configured.. Please try again."

Is this hardcoded to a google API? I want to be able to use any model from my chosen provider, as earlier discussed.