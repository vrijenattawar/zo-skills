Generate API parameters explained

[Jump to Content](https://developers.gamma.app/docs/generate-api-parameters-explained#content)

[![Gamma Generate API](https://files.readme.io/4f9739686130c1d0c18dcaf8b1e252dc5db64483c0a9ae1b60b38b01ce054af8-Gamma_Symbol_White.png)](https://developers.gamma.app/)

[Overview](https://developers.gamma.app/docs)[API Reference](https://developers.gamma.app/reference)[Changelog](https://developers.gamma.app/changelog)v0.2v1.0

---

[Log In](https://developers.gamma.app/login?redirect_uri=/docs/generate-api-parameters-explained)[![Gamma Generate API](https://files.readme.io/4f9739686130c1d0c18dcaf8b1e252dc5db64483c0a9ae1b60b38b01ce054af8-Gamma_Symbol_White.png)](https://developers.gamma.app/)

Overview

[Log In](https://developers.gamma.app/login?redirect_uri=/docs/generate-api-parameters-explained)

v1.0

[Overview](https://developers.gamma.app/docs)[API Reference](https://developers.gamma.app/reference)[Changelog](https://developers.gamma.app/changelog)Generate API parameters explained

All

Pages

###### Start typing to search…

Overview
--------

* [Introduction to Gamma's API offerings](https://developers.gamma.app/docs/getting-started)
* [Understand the API options](https://developers.gamma.app/docs/understand-the-api-options)
* [Generate API parameters explained](https://developers.gamma.app/docs/generate-api-parameters-explained)
* [Create from Template API parameters explained](https://developers.gamma.app/docs/create-from-template-parameters-explained)
* [List Themes and List Folders APIs explained](https://developers.gamma.app/docs/list-themes-and-list-folders-apis-explained)
* [Access and Pricing](https://developers.gamma.app/docs/get-access)
* [Get Help](https://developers.gamma.app/docs/get-help)

Powered by

Generate API parameters explained
=================================

How the the Generate API parameters influence your gamma. Read this before heading to the API Reference page.

The sample API requests below shows all required and optional API parameters, as well as sample responses.

Generate - Quick StartGenerate POST - All ParametersSuccess responseError responseError: No credits

```
curl --request POST \
--url [https://public-api.gamma.app/v1.0/generations](https://public-api.gamma.app/v1.0/generations) \
--header 'Content-Type: application/json' \
--header 'X-API-KEY: <your-api-key>' \
--data '
{
"inputText": "Best hikes in the United States",
"textMode": "generate"
}
'
```

```
curl --request POST \
  --url "https://public-api.gamma.app/v1.0/generations" \
  --header "Content-Type: application/json" \
  --header "X-API-KEY: <your-api-key>" \
  --data '{
    "inputText": "Best hikes in the United States",
    "textMode": "generate",
    "format": "presentation",
    "themeId": "<your-theme-id>",
    "numCards": 10,
    "cardSplit": "auto",
    "additionalInstructions": "Make the titles catchy",
    "folderIds": [
      "<your-folder-id>"
    ],
    "exportAs": "pdf",
    "textOptions": {
      "amount": "detailed",
      "tone": "professional, inspiring",
      "audience": "outdoors enthusiasts, adventure seekers",
      "language": "en"
    },
    "imageOptions": {
      "source": "aiGenerated",
      "model": "imagen-4-pro",
      "style": "photorealistic"
    },
    "cardOptions": {
      "dimensions": "fluid",
      "headerFooter": {
        "topRight": {
          "type": "image",
          "source": "themeLogo",
          "size": "sm"
        },
        "bottomRight": {
          "type": "cardNumber"
        },
        "hideFromFirstCard": true,
        "hideFromLastCard": false
      }
    },
    "sharingOptions": {
      "workspaceAccess": "view",
      "externalAccess": "noAccess",
      "emailOptions": {
        "recipients": [
          "[email protected]"
        ],
        "access": "comment"
      }
    }
  }'
```

```
{
  "generationId": "yyyyyyyyyy"
}
```

```
{
  "message": "Input validation errors: 1. …",
  "statusCode": 400
}
```

```
{
  "message": "Forbidden",
  "statusCode": 403
}
```

GET requestSuccess: status pendingSuccess: status completedError response

```
curl --request GET \
     --url https://public-api.gamma.app/v1.0/generations/yyyyyyyyyy \
     --header 'X-API-KEY: sk-gamma-xxxxxxxx' \
     --header 'accept: application/json'
```

```
{
  "status": "pending",
  "generationId": "XXXXXXXXXXX"
}
```

```
{
  "generationId": "XXXXXXXXXXX",
  "status": "completed",
  "gammaUrl": "https://gamma.app/docs/yyyyyyyyyy",
  "credits":{"deducted":150,"remaining":3000}
}
```

```
{
  "message": "Generation ID not found. generationId: xxxxxx",
  "statusCode": 404,
  "credits":{"deducted":0,"remaining":3000}
}
```

Top level parameters
====================

### `inputText` *(required)*

Content used to generate your gamma, including text and image URLs.

**Add images to the input**

You can provide URLs for specific images you want to include. Simply insert the URLs into your content where you want each image to appear (see example below). You can also add instructions for how to display the images in `additionalInstructions`, eg, "Group the last 10 images into a gallery to showcase them together."

Note: If you want your gamma to use *only* the images you provide (and not generate additional ones), set `imageOptions.source` to `noImages`.

**Token limits**

The token limit is 100,000, which is approximately 400,000 characters. However, in some cases, the token limit may be lower, especially if your use case requires extra reasoning from our AI models. We highly recommend keeping inputText below 100,000 tokens and testing out a variety of inputs to get a good sense of what works for your use case.

**Other tips**

* Text can be as little as a few words that describe the topic of the content you want to generate.
* You can also input longer text -- pages of messy notes or highly structured, detailed text.
* You can control where cards are split by adding \n---\n to the text.
* You may need to apply JSON escaping to your text. Find out more about JSON escaping and [try it out here](https://www.devtoolsdaily.com/json/escape/).

Example

```
"inputText": "Ways to use AI for productivity"
```

Example

```
"inputText": "# The Final Frontier: Deep Sea Exploration\n* Less than 20% of our oceans have been explored\n* Deeper than 1,000 meters remains largely mysterious\n* More people have been to space than to the deepest parts of our ocean\n\nhttps://img.genially.com/5b34eda40057f90f3a45b977/1b02d693-2456-4379-a56d-4bc5e14c6ae1.jpeg\n---\n# Technological Breakthroughs\n* Advanced submersibles capable of withstanding extreme pressure\n* ROVs (Remotely Operated Vehicles) with HD cameras and sampling tools\n* Autonomous underwater vehicles for extended mapping missions\n* Deep-sea communication networks enabling real-time data transmission\n\nhttps://images.encounteredu.com/excited-hare/production/uploads/subject-update-about-exploring-the-deep-hero.jpg?w=1200&h=630&q=82&auto=format&fit=crop&dm=1631569543&s=48f275c76c565fdaa5d4bd365246afd3\n---\n# Ecological Discoveries\n* Unique ecosystems thriving without sunlight\n* Hydrothermal vent communities using chemosynthesis\n* Creatures with remarkable adaptations: bioluminescence, pressure resistance\n* Thousands of new species discovered annually\n---\n# Scientific & Economic Value\n* Understanding climate regulation and carbon sequestration\n* Pharmaceutical potential from deep-sea organisms\n* Mineral resources and rare earth elements\n* Insights into extreme life that could exist on other planets\n\nhttps://publicinterestnetwork.org/wp-content/uploads/2023/11/Western-Pacific-Jarvis_PD_NOAA-OER.jpg\n---\n# Future Horizons\n* Expansion of deep-sea protected areas\n* Sustainable exploration balancing discovery and conservation\n* Technological miniaturization enabling broader coverage\n* Citizen science initiatives through shared deep-sea data"
```

  

### `textMode` *(required)*

Determines how your `inputText` is modified, if at all.

* You can choose between `generate`, `condense`, or `preserve`
* `generate`: Using your `inputText` as a starting point, Gamma will rewrite and expand the content. Works best when you have brief text in the input that you want to elaborate on.
* `condense`: Gamma will summarize your `inputText` to fit the content length you want. Works best when you start with a large amount of text that you'd like to summarize.
* `preserve`: Gamma will retain the exact text in `inputText`, sometimes structuring it where it makes sense to do so, eg, adding headings to sections. (If you do not want any modifications at all, you can specify this in the `additionalInstructions` parameter.)

Example

```
"textMode": "generate"
```

  

### `format` *(optional, defaults to`presentation`)*

Determines the artifact Gamma will create for you.

* You can choose between `presentation`, `document`, `social`, or `webpage`.
* You can use the `cardOptions.dimensions`field to further specify the shape of your output.

Example

```
"format": "presentation"
```

  

### `themeId` *(optional, defaults to workspace default theme)*

Defines which theme from Gamma will be used for the output. Themes determine the look and feel of the gamma, including colors and fonts.

* You can use the [GET Themes](https://developers.gamma.app/v1.0/update/docs/list-themes-and-folders-apis#/) endpoint to pull a list of themes from your workspace. Or you can copy over the themeId from the app directly.

![](https://files.readme.io/d01171ca7562e427d8469ee2d0391e54400235ca558d6da8e61cf35e957d8833-CleanShot_2025-11-03_at_14.24.272x.png)
  

Example

```
"themeId": "abc123def456ghi"
```

  

### `numCards` *(optional, defaults to`10`)*

Determines how many cards are created if `auto` is chosen in `cardSplit`

* Pro users can choose any integer between 1 and 60.
* Ultra users can choose any integer between 1 and 75.

Example

```
"numCards": 10
```

  

### `cardSplit` *(optional, defaults to`auto`)*

Determines how your content will be divided into cards.

* You can choose between `auto` or `inputTextBreaks`
* Choosing `auto` tells Gamma to looks at the `numCards` field and divide up content accordingly. (It will not adhere to text breaks \n---\n in your `inputText`.)
* Choosing `inputTextBreaks` tells Gamma that it should look for text breaks \n---\n in your `inputText` and divide the content based on this. (It will not respect `numCards`.)
  + Note: One \n---\n = one break, ie, text with one break will produce two cards, two break will produce three cards, and so on.
* Here are some scenarios to guide your use of these parameters and explain how they work

| inputText contains \n---\n and how many | cardSplit | numCards | output has |
| --- | --- | --- | --- |
| No | auto | 9 | 9 cards |
| No | auto | left blank | 10 cards (default) |
| No | inputTextBreaks | 9 | 1 card |
| Yes, 5 | auto | 9 | 9 cards |
| Yes, 5 | inputTextBreaks | 9 | 6 cards |

Example

```
"cardSplit": "auto"
```

  

### `additionalInstructions` *(optional)*

Helps you add more specifications about your desired output.

* You can add specifications to steer content, layouts, and other aspects of the output.
* Works best when the instructions do not conflict with other parameters, eg, if the `textMode` is defined as `condense`, and the `additionalInstructions` say to preserve all text, the output will not be able to respect these conflicting requests.
* Character limits: 1-2000.

Example

```
"additionalInstructions": "Make the card headings humorous and catchy"
```

  

### `folderIds` *(optional)*

Defines which folder(s) your gamma is stored in.

* You can use the [GET Folders](https://developers.gamma.app/v1.0/update/docs/list-themes-and-folders-apis#/) endpoint to pull a list of folders. Or you can copy over the folderIds from the app directly.

![](https://files.readme.io/eefcb9b3f6404e96978f1a92aed2820c178ed1dbf550873c6e3da0538c466740-CleanShot_2025-11-03_at_14.27.362x.png)
  

* You must be a member of a folder to be able to add gammas to that folder.

Example

```
"folderIds": ["123abc456def", "456123abcdef"]
```

  

### `exportAs` *(optional)*

Indicates if you'd like to return the generated gamma as a PDF or PPTX file as well as a Gamma URL.

* Options are `pdf` or `pptx`
* Download the files once generated as the links will become invalid after a period of time.
* If you do not wish to directly export to a PDF or PPTX via the API, you may always do so later via the app.

Example

```
"exportAs": "pdf"
```

  

textOptions
===========

### `textOptions.amount` *(optional, defaults to`medium`)*

Influences how much text each card contains. Relevant only if `textMode` is set to `generate` or `condense`.

* You can choose between `brief`, `medium`, `detailed` or `extensive`

Example

```
"textOptions": {
    "amount": "detailed"
  }
```

  

### `textOptions.tone` *(optional)*

Defines the mood or voice of the output. Relevant only if `textMode` is set to `generate`.

* You can add one or multiple words to hone in on the mood/voice to convey.
* Character limits: 1-500.

Example

```
"textOptions": {
    "tone": "neutral"
  }
```

Example

```
"textOptions": {
    "tone": "professional, upbeat, inspiring"
  }
```

  

### `textOptions.audience` *(optional)*

Describes who will be reading/viewing the gamma, which allows Gamma to cater the output to the intended group. Relevant only if `textMode` is set to `generate`.

* You can add one or multiple words to hone in on the intended viewers/readers of the gamma.
* Character limits: 1-500.

Example

```
"textOptions": {
    "audience": "outdoors enthusiasts, adventure seekers"
  }
```

Example

```
"textOptions": {
    "audience": "seven year olds"
  }
```

  

### `textOptions.language` *(optional, defaults to`en`)*

Determines the language in which your gamma is generated, regardless of the language of the `inputText`.

* You can choose from the languages listed [here](https://developers.gamma.app/reference/output-language-accepted-values).

Example

```
"textOptions": {
    "language": "en"
  }
```

  

imageOptions
============

### `imageOptions.source` *(optional, defaults to`aiGenerated`)*

Determines where the images for the gamma are sourced from. You can choose from the options below. If you are providing your own image URLs in `inputText` and want only those to be used, set `imageOptions.source` to `noImages` to indicate that Gamma should not generate additional images.

| Options for `source` | Notes |
| --- | --- |
| `aiGenerated` | If you choose this option, you can also specify the `imageOptions.model` you want to use as well as an `imageOptions.style`. These parameters do not apply to other `source` options. |
| `pictographic` | Pulls images from Pictographic. |
| `unsplash` | Gets images from Unsplash. |
| `giphy` | Gets GIFs from Giphy. |
| `webAllImages` | Pulls the most relevant images from the web, even if licensing is unknown. |
| `webFreeToUse` | Pulls images licensed for personal use. |
| `webFreeToUseCommercially` | Gets images licensed for commercial use, like a sales pitch. |
| `placeholder` | Creates a gamma with placeholders for which images can be manually added later. |
| `noImages` | Creates a gamma with no images. Select this option if you are providing your own image URLs in `inputText` and want only those in your gamma. |

  

Example

```
"imageOptions": {
    "source": "aiGenerated"
  }
```

  

### `imageOptions.model` *(optional)*

This field is relevant if the `imageOptions.source` chosen is `aiGenerated`. The `imageOptions.model` parameter determines which model is used to generate images.

* You can choose from the models listed [here](https://developers.gamma.app/reference/image-model-accepted-values).
* If no value is specified for this parameter, Gamma automatically selects a model for you.

Example

```
"imageOptions": {
	"model": "flux-1-pro"
  }
```

  

### `imageOptions.style` *(optional)*

This field is relevant if the `imageOptions.source` chosen is `aiGenerated`. The `imageOptions.style` parameter influences the artistic style of the images generated. While this is an optional field, we highly recommend adding some direction here to create images in a cohesive style.

* You can add one or multiple words to define the visual style of the images you want.
* Adding some direction -- even a simple one word like "photorealistic" -- can create visual consistency among the generated images.
* Character limits: 1-500.

Example

```
"imageOptions": {
	"style": "minimal, black and white, line art"
  }
```

  

cardOptions
===========

### `cardOptions.dimensions` *(optional)*

Determines the aspect ratio of the cards to be generated. Fluid cards expand with your content. Not applicable if `format` is `webpage`.

* Options if `format` is `presentation`: `fluid` **(default)**, `16x9`, `4x3`
* Options if `format` is `document`: `fluid` **(default)**, `pageless`, `letter`, `a4`
* Options if `format` is `social`: `1x1`, `4x5`**(default)** (good for Instagram posts and LinkedIn carousels), `9x16` (good for Instagram and TikTok stories)

Example

```
"cardOptions": {
  "dimensions": "16x9"
}
```

  

### `cardOptions.headerFooter` *(optional)*

Allows you to specify elements in the header and footer of the cards. Not applicable if `format` is `webpage`.

* Step 1: Pick which positions you want to populate. Options: `topLeft`, `topRight`, `topCenter`, `bottomLeft`, `bottomRight`, `bottomCenter`.
* Step 2: For each position, specify what type of content goes there. Options: `text`, `image`, and `cardNumber`.
* Step 3: Configure based on type.
  + For `text`, define a `value` (required)
  + For `image`:
    - Set the `source`. Options: `themeLogo` or `custom`image (required)
    - Set the `size` . Options:`sm`, `md`, `lg`, `xl` (optional)
    - For a`custom` image, define a `src` image URL (required)
  + For `cardNumber`, no additional configuration is available.
* Step 4: For any position, you can control whether it appears on the first or last card:
  + `hideFromFirstCard` (optional) - Set to `true` to hide from first card. Default: `false`
  + `hideFromLastCard` (optional) - Set to `true` to hide from last card. Default: `false`

Example

```
"cardOptions": {
    "headerFooter": {
      "topRight": {
        "type": "image",
        "source": "themeLogo",
        "size": "sm"
      },
      "bottomRight": {
        "type": "cardNumber",
      },
      "hideFromFirstCard": "true"
    },
}
```

Example

```
"cardOptions": {
    "headerFooter": {
      "topRight": {
        "type": "image",
        "source": "custom",
        "src": "https://example.com/logo.png",
        "size": "md"
      },
      "bottomRight": {
        "type": "text",
        "value": "© 2025 Company™"
      },
      "hideFromFirstCard": "true",
      "hideFromLastCard": "true"
    },
}
```

  

sharingOptions
==============

### `sharingOptions.workspaceAccess` *(optional, defaults to workspace share settings)*

Determines level of access members in your workspace will have to your generated gamma.

* Options are: `noAccess`, `view`, `comment`, `edit`, `fullAccess`
* `fullAccess`allows members from your workspace to view, comment, edit, and share with others.

Example

```
"sharingOptions": {
	"workspaceAccess": "comment"
}
```

  

### `sharingOptions.externalAccess` *(optional, defaults to workspace share settings)*

Determines level of access members **outside your workspace** will have to your generated gamma.

* Options are: `noAccess`, `view`, `comment`, or `edit`

Example

```
"sharingOptions": {
	"externalAccess": "noAccess"
}
```

  

### `sharingOptions.emailOptions` *(optional)*

#### `sharingOptions.emailOptions.recipients` *(optional)*

Allows you to share your gamma with specific recipients via their email address.

Example

```
"sharingOptions": {
  "emailOptions": {
    "recipients": ["[email protected]", "[email protected]"]
}
```

#### `sharingOptions.emailOptions.access` *(optional)*

Determines level of access those specified in `sharingOptions.emailOptions.recipients` have to your generated gamma. Only workspace members can have `fullAccess`

* Options are: `view`, `comment`, `edit`, or `fullAccess`

Example

```
"sharingOptions": {
  "emailOptions": {
    "access": "comment"
}
```

Updated 1 day ago

---

Read More

* [Create from Template API parameters explained](https://developers.gamma.app/docs/create-from-template-parameters-explained)

Ask AI