# E3: answers the judge called incorrect, and what the verifiers said

Phase-A answers (200, WixQA expert-written) judged against the reference by Sonnet; the verifiers never see the reference.
Source: `repeat-verified` (Haiku verifier) and `repeat-verified-sonnet` (Sonnet verifier). Node text is the current text, first 400 characters.

## Haiku verifier vs judge

| Verifier | correct | partial | incorrect | total |
|---|---|---|---|---|
| supported | 88 | 36 | 10 | 134 |
| unsupported | 29 | 26 | 11 | 66 |

## Sonnet verifier vs judge

| Verifier | correct | partial | incorrect | total |
|---|---|---|---|---|
| supported | 100 | 41 | 10 | 151 |
| unsupported | 17 | 21 | 11 | 49 |

## The 21 judge-incorrect answers

### wixqa_expertwritten-0009

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

I couldn’t link PayPal to my site because the option to connect to PayPal was not available. I confirmed that I have a PayPal Business account and adjusted my business location in the Wix dashboard.

**Reference answer**

There are 2 main reasons for payment providers not appearing in the Accept Payments tab:
  
  1. Different payment providers are available in different locations. PayPal is available in around 200 countries. Please check the following link to make sure PayPal is available in your location: [visit PayPal] (https://www.paypal.com/pn/webapps/mpp/country-worldwide).
  
  
  2. If you began onboarding with Wix Payments, you may have selected a prohibited product or service. If so, this may remove the option to onboard with other payment providers who prohibit similar items. 
  
  For more information, please see [our checklist for restricted products & services when setting up your payments] (https://support.wix.com/en/article/checking-for-restricted-products-services-when-setting-up-your-payments).
  
  If you mistakenly completed a CBD declaration, or selected a restricted product/service, please contact [Wix Customer Care] (https://www.wix.com/contact).

**Phase-A answer**

The docs I found don't cover the "option not available" case directly, so I can't confirm the cause from them. Here's what they do say:

- **Region:** PayPal connection is only offered "if PayPal is available in your region" (n2462). PayPal payments are also no longer supported for businesses based in Russia (n2461).
- **Business location:** Go to Accept Payments in your site's dashboard and check the business location at the top right. If it's wrong, use the drop-down to change it (n2463). Since you already changed it, make sure the Accept Payments page reflects the new location and refresh it.
- **Account type:** You need a PayPal Business account (not Personal). You can check this in your PayPal dashboard (n5665).
- **Connecting:** Click Connect next to PayPal, enter the email linked to your PayPal Business account, sign in to PayPal, then click "Go back to Wix.com" to finish (n2464).

If the option still doesn't appear, the docs don't list further troubleshooting steps. Contacting Wix support would be the next step.

**Cited nodes**

- `n2462` (articles/ › Other/ › Connecting PayPal as a Payment Provider › Connecting PayPal): ## Connecting PayPal  If PayPal is available in your region and you choose to connect it, you can either connect an existing PayPal business account or create a new one.
- `n2463` (articles/ › Other/ › Connecting PayPal as a Payment Provider › To connect PayPal:): ## To connect PayPal:  - Go to Accept Payments in your site's dashboard. Tip: Check your business location at the top right. If incorrect, click the drop-down menu to change it.  - Click Connect next to PayPal.  - Depending on whether you have a PayPal business account or need to create a new one, follow the steps:  #### Have a PayPal business account  - Enter the email address associated with you
- `n5665` (articles/ › Other/ › Troubleshooting Pending PayPal Payments › Check that you have a PayPal Business account): #### Check that you have a PayPal Business account  In order to accept PayPal payments through your Wix site, you need a PayPal Business account. Log in to your PayPal dashboard to confirm if you have a Business account. If you do not have a PayPal Business account, you can change your account type to accept payments through Wix.
- `n2461` (articles/ › Other/ › Connecting PayPal as a Payment Provider): # Connecting PayPal as a Payment Provider  Important:  As of March 7 2022, Wix no longer supports PayPal payments for any businesses, both new and existing, based in Russia.  A PayPal business account is a great alternative to opening a credit card merchant account. Using PayPal you can accept PayPal payments, credit cards and debit cards. Customers are directed to PayPal when making the payment. 

### wixqa_expertwritten-0011

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

I have created pages in the Wix editor, but they are not showing up on the live site even though I have hit publish. I have made sure the pages are not hidden and they are published, but they are still not showing up on the live site.

**Reference answer**

If your pages are not showing up on the live site even after publishing, here are some steps you can take to troubleshoot the issue:
  
  1) If you are receiving any errors while publishing please review this [article](https://support.wix.com/en/article/wix-editor-publishing-issues) for more information. 
  2) Make sure you are using a supported browser. Outdated browsers can cause rendering issues. [Check supported browsers](https://support.wix.com/en/article/supported-browsers).
  3) If the issue persists, use the [Wix Technical Assistant](https://support.wix.com/en/article/wix-technical-assistant) for further troubleshooting.

**Phase-A answer**

The docs don't have a section that matches your exact situation, so these are the closest checks they suggest:

1. **Publish again after the last change.** Saving doesn't make changes live; you have to click Publish at the top right of the editor, then View Site to check (n9139).

2. **Check that the page is shown in the menu.** "Hidden" in the menu is separate from the page being published. In the editor, go to Pages & Menu, click the More Actions icon next to the page, and select "Show in menu" (n8862). A Hidden icon marks hidden pages in that panel. If every page is hidden on mobile, use the More Actions icon and choose "Show on mobile" (n9324).

3. **Check the header and footer layout.** If the menu is attached to the header or footer, or set to "show on all pages," make sure the page's layout isn't hiding them. Set Settings > Layouts to Standard, then Publish (n9067).

4. **Wait for domain propagation if the site is new or the domain was just connected.** During propagation, published changes may not appear on the live site. If you still can't see the site after 48 hours, check your DNS records at whatsmydns.net (n34).

If none of these fix it, the docs don't cover this case. Contact Wix support with the page name and the time you published.

**Cited nodes**

- `n9139` (articles/ › Wix Editor/ › Wix Editor: Publishing Your Site › To publish your site:): ## To publish your site:  - Click Publish at the top right of the editor.  - (Optional) Click View Site to see your live site.  - Click Done to return to the editor.  Note:  Clicking Save won't make your changes live. After saving, make sure to click Publish to show the updates on your live site.
- `n9067` (articles/ › Wix Editor/ › Wix Editor: Menu Issues › To resolve issues with your site's menu click below: › Menu missing on live site): #### Menu missing on live site  If you cannot view your menu on your live site, try the following:  - Make sure you've added a menu to your site. Learn How  - If your menu is attached to the header or footer, or set to "show on all pages," make sure you are not hiding the header and footer:  - Click Menus & Pages on the left side of the Editor.  - Click the relevant page that isn't displaying your
- `n34` (articles/ › Other/ › About Domain Propagation › During the domain propagation process:): ## During the domain propagation process:  - You may not be able to view your live site online.  - Your previously connected live site may appear on your domain.  - You may not receive emails connected to your domain.  - Published changes to your site may not appear on your live site.  - Your site may appear correctly in one browser or computer, but not in another.  - The SSL certificate will only
- `n8862` (articles/ › Wix Editor/ › Wix Editor: Hiding and Unhiding a Page From Your Site Menu › To unhide a page from your menu:): ## To unhide a page from your menu:  - Go to your editor.  - Click Pages & Menu on the left side of the editor.  - Click the More Actions icon next to the relevant hidden page. Tip: A Hidden icon indicates hidden pages in this panel.  - Select Show in menu .
- `n9054` (articles/ › Wix Editor/ › Wix Editor: Managing Your Site Pages › To manage your site pages: › Hide the page from the menu): #### Hide the page from the menu  Click Hide to hide a page to keep it accessible for future use without displaying it in the site's navigation.  Tip:  To unhide, click the More Actions icon next to the hidden page and select Show .
- `n9324` (articles/ › Wix Editor/ › Wix Editor: Troubleshooting an Unresponsive Mobile Menu › Click your issue below to find the solution: › All the pages are hidden): #### All the pages are hidden  Your menu is not responsive if all of the pages are hidden from the mobile site.  In order to resolve this issue, you need to show pages on your site menu.  To show pages on your mobile site:  - Click Menus & Pages on the left side of the mobile Editor.  - Click the relevant page.  - Click the More Actions icon .  - Click Show on mobile .

### wixqa_expertwritten-0033

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

I received a manual payment from the pay button and I am unable to see the payment history.

**Reference answer**

If you're receiving payments using the manual (offline) method, you must mark them as paid before they appear in your payments page. Manual payments appear in your Payments tab once they have been marked as Paid. 

You can track payments through your Wix site dashboard. [Go to All Payments] (https://www.wix.com/my-account/site-selector/?buttonText=Go%20to%20Payments&title=Select%20a%20Site&autoSelectOnSingleSite=true&actionUrl=https:%2F%2Fwww.wix.com%2Fdashboard%2F%7B%7BmetaSiteId%7D%7D%2Fpayments-dashboard/?referralInfo=KB_Article) in your site's dashboard to view all transactions.

It is not possible to refund, delete or change the status of any manual payment from the Payments tab.

**Phase-A answer**

Payments made through the Pay Button should appear in your site's dashboard. Go to **All Payments** in the dashboard to view all transactions, including the manual payment you received [n594].

The docs don't say why a payment would be missing from that list. If it doesn't show up under All Payments, the docs I found don't cover that case, so you'd need to contact Wix Support.

**Cited nodes**

- `n594` (articles/ › Other/ › Adding and Setting Up a Pay Button › FAQs › Is it possible to track payments made through the Pay Button?): #### Is it possible to track payments made through the Pay Button?  Yes, you can track payments through your Wix site dashboard. Go to All Payments in your site's dashboard to view all transactions.

### wixqa_expertwritten-0053

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

I would like to change my billing cycle from 2 years to monthly payments.

**Reference answer**

To change your billing cycle to monthly, please follow these instructions:
  Go to [Premium Subscriptions] (https://manage.wix.com/studio/subscriptions?originWidgetName=billings) in your Wix account.
  Click the More Actions icon next to the relevant plan. 
  Click Change Billing Cycle.
  Select your new billing cycle.
  Click Continue.
  Review your billing information and click Confirm.
  Please keep in mind that if you switch to a shorter plan cycle, your billing cycle will switch over on the date when your current cycle ends.

**Phase-A answer**

The docs don't clearly confirm that a 2-year plan can be switched to monthly billing, so I can't give you a definite yes.

What the docs say:
- Wix lets you change your billing cycle and keep your current plan by changing the subscription period. Monthly, yearly, and multi-year (2 or 3 years) cycles are all listed. (n6479, n4949)
- The docs describe switching from a yearly to a monthly cycle to make payments more manageable. They don't mention switching from a 2-year plan specifically. (n1028)
- A 2-year plan is charged once every two years for the full period. (n4754)
- One section says that once you select a payment cycle, you can't change it, and gives yearly-to-monthly as an example. That contradicts the switching sections above. (n15235)

I'd suggest checking the "change the subscription period" steps in your Wix account, or contacting Wix support to confirm whether your 2-year plan can move to monthly billing and whether any refund or credit applies.

**Cited nodes**

- `n6479` (articles/ › Other/ › Wix Billing for Site Plans › FAQs › Can I change my billing cycle?): #### Can I change my billing cycle?  Yes. You can change your billing subscription cycle from yearly to monthly, or from monthly to yearly. Learn how to change your billing cycle.
- `n1028` (articles/ › Other/ › Canceling a Wix Premium or Studio Plan › Switching to a monthly billing cycle): ## Switching to a monthly billing cycle  Switch from a yearly to a monthly billing cycle to make payments more manageable. While our longer-term plans offer great savings, with a monthly plan you don't have to commit to a long-term subscription. Learn more about changing the subscription period of your plan.
- `n15235` (articles/ › Google Workspace/ › Google Workspace: Auto Renewal and Payment Issues for Your Business Email › Resolving Declined Payment Issues): ## Resolving Declined Payment Issues  To resolve the payment issue, please update your payment method to complete the payment, by following the instructions here.  Alternatively, please contact your bank or credit card company to check why the payment failed.  If your Google Workspace business email service has been canceled due to payment problems, you can repurchase by following the instructions
- `n4754` (articles/ › Other/ › Purchasing a 2 or 3 Year Plan): # Purchasing a 2 or 3 Year Plan  Our multi-year Premium plans and Studio plans offer great savings over the yearly or monthly subscriptions.  If you purchase a multi-year subscription, you are charged for the entire subscription period. To prevent service disruption, your plan will renew automatically and you will be charged at the end of your initial subscription period. For example, if you purch
- `n6473` (articles/ › Other/ › Wix Billing for Site Plans): # Wix Billing for Site Plans  We offer Premium plans and Studio plans for sites built with Wix. Plan subscriptions have different billing cycles for you to choose from. Longer term plans offer better savings and additional benefits (e.g. a domain voucher), whereas shorter term plans give you more flexibility.  - Monthly subscription: You are charged on a monthly basis.  - Yearly subscription: You 
- `n4949` (articles/ › Other/ › Requesting a Refund for a Premium or Studio Plan › FAQs › I accidentally purchased the wrong plan. Can I change it?): #### I accidentally purchased the wrong plan. Can I change it?  Yes, you can change to a different plan or different subscription period. For example, you can change:  - From a Monthly Core plan to Monthly Business plan  - From a Monthly Business plan to Yearly Business plan  If you change to a cheaper plan, you will be credited the difference.  Learn more about changing your plan.

### wixqa_expertwritten-0056

- Haiku verifier: **supported**
- Sonnet verifier: **unsupported**

**Question**

I would like to know how many sites I can have.

**Reference answer**

With Wix, you're not just limited to creating a single site. You can create as many as you need to manage multiple businesses, separate your personal site or blog, or experiment with different designs. 

If you reach the limit of free sites you can have within your account, you can [move old sites to trash] (https://support.wix.com/en/article/moving-a-site-to-trash) or [upgrade your sites to Premium] (https://support.wix.com/en/article/upgrading-your-site-to-premium-3066683).

**Phase-A answer**

The docs I searched don't state a maximum number of sites for an account.

The closest answer is about Wix Studio workspaces: you can belong to up to 50 workspaces, and once you reach 50 you can't create new ones. Within each workspace you can create as many sites as you want. (n30279)

If you meant a general Wix account, the docs I found don't cover that limit. Checking your plan details or Wix support would be the next step.

**Cited nodes**

- `n30279` (articles/ › Wix Studio FAQs/ › Wix Studio FAQs: Using the Workspace › Workspace features › How many workspaces can I have in Wix Studio? Is there a limit?): #### How many workspaces can I have in Wix Studio? Is there a limit?  If you belong to 50 workspaces, you will not be able to create any new ones. You can create as many sites as you want within each workspace.

### wixqa_expertwritten-0069

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

Im experiencing trouble with the website editor. Theres a stray logo on the published version that doesnt show up in the editor, making it impossible to correct.

**Reference answer**

If you are unable to select or find an element in the editor, it is possible that it has been placed behind another element. Follow the steps below to locate and select your elements in the editor.

## Use the Layers panel to locate an element
If an element is placed outside the editor gridlines or behind another element, you may not be able to see it on your screen. Use the Layers panel to locate the element on the page.
## To open the Layers panel and find elements:
1. [Go to your editor](https://manage.wix.com/account/site-selector/?actionUrl=https%3A%2F%2Fwww.wix.com%2Feditor%2F%7BmetaSiteId%7D%3FeditorSessionId%3D%7Besi%7D%26).
2. Click the **Layers** icon ![](https://lh6.googleusercontent.com/gK9dfcU80SWT9YOMhPhN62hW4YUDMmaf17w7O0LfSHLFn46W1Nugy_36zibPxclwtc5OmziXxiJ-zGwzz956EAjx8MqPYVd_i7KRCOZU9Sq7-7KUE-tjh3C5Lhgyto4oz9h2J5E5-59p__W4gjiJwg) at the bottom of your editor.
3. Click **Header**, **Page** or **Footer**.
4. Find the relevant element on the list and click to select it.

## Use Ctrl + Shift + M to toggle through your elements
If you see an element on your live site or in Preview mode, but not in the editor, it might be placed outside of the site's gridlines. Toggle through your page elements to locate the element.
To toggle through elements on a page:
1. Hold down Ctrl (Cmd on Mac) + Shift on your keyboard.
2. Press M to scroll through the elements on your site until you reach the desired element.

**Phase-A answer**

I couldn't find a help article about a stray logo that appears on the published site but not in the editor. The searches returned only unrelated logo-maker and language-menu articles.

Two docs describe editor-versus-live differences that might be worth checking:
- **Hidden secondary language:** if a language menu shows in the editor but not on the live site, the secondary language may be hidden. Set its status to Visible in Multilingual, then click Publish.
- **Element visibility by device:** some elements can be shown or hidden per device (All, Android, or iOS) in the element's settings, followed by Save & Publish.

Neither is confirmed to match your logo. Since the editor doesn't show the element, I'd contact Wix Support and describe where the logo appears on the live site.

I haven't recorded this path because it doesn't rest on a documented fix for your issue.

**Cited nodes**

- (none)

### wixqa_expertwritten-0076

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

Im having trouble updating the terms & conditions checkbox at checkout in Wix Stores. I confirmed that I have a "Products" section in my sites dashboard.

**Reference answer**

To update the terms & conditions checkbox at checkout in Wix Stores, you can follow these steps:

1. Go to your site's dashboard and navigate to the Checkout Settings.
2. Click on 'Customize your checkout'.
3. Click on 'Policies'.
4. Select the checkbox next to the 'Terms & Conditions' policy you want to display.
5. Enter the policy text.
6. To make it mandatory for customers to agree to these terms before completing checkout, enable the 'Policy agreement checkbox' toggle.

Tip:
As soon as you select the checkbox next to a policy and enter text, it's displayed in the footer of your Checkout Page.

**Phase-A answer**

I couldn't find step-by-step instructions for the Terms & Conditions checkbox in Wix Stores, so I can't tell you exactly why your update isn't saving.

What the docs do cover:

- **Checkout policies apply to Stores orders.** The help article "Improve customer experience with clear checkout policies" says these policies appear as links in the checkout footer, and can optionally sit next to a checkbox that customers must tick before checking out. It also notes that checkout policies apply to orders that contain products. (n11984)
- **The docs I found for the checkbox itself are for other products.** The "Add Terms & Conditions" steps (Link to URL or Paste as text) are from the Wix Restaurants article, and the "Add a policy" steps with the Policy checkbox toggle are from Bookings/pricing plans. Neither is a Stores checkout guide, so I didn't use them as instructions.
- **Online Programs can't use the checkbox.** The docs say you can't add a Terms & Conditions checkbox to the Online Programs checkout.

Next steps:

1. Check the checkout policy settings in your dashboard's Products or Checkout area, and make sure the policy is saved and the checkbox option is turned on.
2. If the option is missing or won't save, contact Wix Support and mention the Stores checkout policy checkbox. Include a screenshot of the setting and any error message.

**Cited nodes**

- `n11984` (articles/ › Wix Bookings/ › Wix Bookings: Understanding Your Checkout Settings › Improve customer experience with clear checkout policies): ## Improve customer experience with clear checkout policies  Display your business policies on your checkout page, so customers know exactly what to expect as they check out.  These policies appear:  - As clickable links in the footer of your checkout page  - (Optional) Next to a policy checkbox that customers must agree to before checking out.  Learn more about adding eCommerce policies, terms an

### wixqa_expertwritten-0080

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

What are the collection limits in Wix Store?

**Reference answer**

To ensure that the Wix Stores platform remains stable and that your online store is usable and fast, Wix has set the following limitations:
  
  - Products: You can upload up to 50,000 products from the Wix Stores Dashboard manually or by CSV import.
  - Product Options per Product: Each product can have up to 6 product options (e.g. color, size, material).
  - Choices per Product Option: Each product option (e.g. size) can have up to 100 option choices (e.g. Green, Blue)
  - Product Variants: You can create up to 1,000 variants per product.

**Phase-A answer**

The docs I found cover CMS collections (the data collections on a Wix site, including those used with stores) rather than store-specific limits, so this may not be exactly what you meant:

- **Items:** You can create up to 10,000 items in a collection. This limit applies only to collections you create, not to collections created by Wix apps. (n19106)
- **Storage per item:** A single item can hold up to 500KB of data across its collection fields. Image, document, multi-document, video, audio, and media gallery fields are excluded from this limit. (n19000, n30612)
- **Number fields:** Values must be between -2147483647 and 2147483647. (n19027)
- **Image fields:** Accepted formats are JPG, PNG, SVG, and GIF, with a maximum size of 25 MB. (n19027)

The docs don't say whether these limits apply identically to store product data. If you need store-specific limits, such as product or variant caps, I can search for those.

**Cited nodes**

- `n19000` (articles/ › CMS/ › CMS: Managing Your Collection Content › FAQs › Are there storage limits for collection fields?): #### Are there storage limits for collection fields?  Yes. You can store up to 500KB of data in a single item's total collection fields. This limit does not apply to image, document, multi document, video, audio, or media gallery fields. Click here to vote for increasing the storage limits.
- `n30612` (feature-requests/ › CMS/ › CMS Request: Increasing the Total Field Storage Limit for an Item in a Collection): # CMS Request: Increasing the Total Field Storage Limit for an Item in a Collection  Currently, there is a limit to how much data you can store in a single item's combined collection fields. You can store up to 500KB of data in an item's total collection fields.  This limit does not apply to image, document, multi document, video, audio, or media gallery fields. Learn more about the limitations of
- `n19106` (articles/ › CMS/ › CMS: Getting a Custom Quota to Increase Your Collection Item Limits › Does the 10,000 collection item limit include Wix app collections?): #### Does the 10,000 collection item limit include Wix app collections?  The 10,000 collection item limit specifically applies to collections you create. This means it does not extend to collections created by Wix apps. This limit offers plenty of room to develop your site, without impacting the available space for your apps, products, and CRM contacts and members. If you need to expand your colle
- `n19027` (articles/ › CMS/ › CMS: Supported Content in Collection Field Types › Content limitations for each collection field type): ## Content limitations for each collection field type  View each field type's content limitations in the table below:  Field Type  Content Limitations  Text  Store plain text for use with titles, descriptions, and other text-based content.  Image  Store the following types of image files: JPG, PNG, SVG, and GIF  You can add images to fields by pasting their image URLs in the fields.  Max size: 25 

### wixqa_expertwritten-0110

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

The picture on my mobile site is dark. Its a standalone image that was carried over from my desktop site. I need guidance on adjusting the image settings for my mobile site.

**Reference answer**

To adjust the settings of a standalone image that was carried over from your desktop site to your mobile site, you can follow these steps:
  1. Click the Settings icon .
  2. Customize the following:
  - Image Behaviors: Decide how your visitors interact with images.
  - When an image is tapped: 
  - Nothing happens: The image is not clickable, nothing happens when it's clicked.
  - A link opens: The image acts as a button and can be linked to a page, anchor on your site, an external URL, and more. 
  - It opens in a popup: The image opens in a pop-up window.
  - Image Resizing: Decide what happens when your images are resized.
  - Keep Proportions: The image and shape stay at the original proportions when resized.
  - Auto-fill: The image automatically adjusts to fill the space on your visitor's device.
  
  You can also add and customize mobile-only images to replace the picture with a lighter one. Follow these steps to do it: 
  
  1. Click Add to Mobile on the left of the mobile Editor.
  2. Click Image.
  3. Select the image type you want to add.
  4. Click the image you want to upload and click Add to Page.

**Phase-A answer**

Your image was carried over from desktop, so you can adjust it in the mobile editor without changing the desktop version. Mobile changes don't affect the desktop view.

Per the Wix docs, for an image carried over from desktop you can:
- Customize its settings, such as scroll effects and positioning, to control how it displays on mobile.
- Crop it.
- Add an animation to make it different from the desktop version.

To get there, open the mobile editor and select the image. Carried-over images have limited customization compared with images you add in the mobile editor, so the docs don't describe a specific brightness or exposure control for them.

For brightness, the docs describe the Edit Media tools in the Wix app (Media Manager → More Actions → Edit Media → Adjust), which cover brightness, saturation, and highlights. The docs don't say whether these apply to a mobile-only copy of a carried-over image, so check that in your editor. If the option isn't there, the docs don't offer another route, and you may need to contact Wix support.

**Cited nodes**

- `n7438` (articles/ › Wix Editor/ › Wix Editor: Adding and Customizing Images on Your Mobile Site › Images carried over from your desktop version): ## Images carried over from your desktop version  Images you add to the desktop version of your site are automatically carried over to your mobile site. You can customize the image's settings, crop it, and add an animation to make it different from the desktop version.
- `n7197` (articles/ › Wix Editor/ › Wix Editor: About the Mobile Version of Your Site › FAQs › Can I customize my mobile site separately?): #### Can I customize my mobile site separately?  Absolutely. You can use the mobile editor to manage and adjust desktop elements, add and customize mobile-only elements, and add mobile tools.
- `n8378` (articles/ › Wix Editor/ › Wix Editor: Cropping and Setting Up Your Mobile Image Background › Adjusting the settings of your mobile background image): ## Adjusting the settings of your mobile background image  As well as cropping your image, you can also change settings such as its scroll effects and positioning to set how it's displayed on your mobile site.
- `n12790` (articles/ › Wix Events/ › Wix Events: Changing the Event List Layout › Setting the layout for the mobile view): ## Setting the layout for the mobile view  You can set the mobile layout from both the Wix Editor and Studio Editor. Desktop layout settings apply to mobile, but you can customize the mobile view separately.  In the Wix Editor, select from 2 mobile-optimized layouts to adjust how images appear. In the Studio Editor, you can edit layouts for both tablet and mobile breakpoints.  Notes:  - Mobile lay

### wixqa_expertwritten-0115

- Haiku verifier: **supported**
- Sonnet verifier: **unsupported**

**Question**

User is inquiring about setting up the website to require an account for placing orders.

**Reference answer**

You can limit guest checkout on your site so that visitors can browse what you offer, but need to become site members before they can access the Cart Page to begin the checkout process. 
  
 [Go to your editor.] (https://manage.wix.com/account/site-selector/?actionUrl=https%3A%2F%2Fwww.wix.com%2Feditor%2F%7BmetaSiteId%7D%3FeditorSessionId%3D%7Besi%7D%26)
Click Pages & Menu  on the left side of the editor.
Select an option:
My site has only Wix Stores:
Click Store Pages.
Click Cart Page.
My site has only Wix Bookings:
Click Bookings Pages.
Click Cart Page.
My site has Wix Restaurants Orders (New) or 2 business solutions:
Click Cart & Thank You.
Click Cart Page.
Click the Settings icon  next to Cart Page. 
Select the Permissions tab.
Click Members Only.
Decide Which members can access this page:
All members.
Only selected members or paying customers: Limit access to a [member role you created] (https://support.wix.com/en/article/requiring-customers-to-sign-up-before-making-purchases#:~:text=customers%3A%20Limit%20access%20to%20a-,member%20role%20you%20created,-or%20to%20clients%20who%20have) or to clients who have purchased a [pricing plan] (https://support.wix.com/en/article/pricing-plans-an-overview).

**Phase-A answer**

The docs I found don't include a setting that makes account login mandatory for placing orders, so I can't give you exact steps for that.

What they do cover:
- **Members Area:** Adding a Members Area lets customers sign up and log in. Their details are saved after the first purchase, so repeat checkouts are faster (Fast Checkout, n46). Since Members Area is what enables customer accounts, it's the piece you'd set up first. The docs don't say whether it can be made a requirement for checkout.
- **Guest checkout:** The PayPal guest checkout article (n17418) describes customers paying without a PayPal account. It doesn't address whether your store can turn off guest checkout on your site.

If you need a definite answer, check Wix's support for requiring login at checkout, or contact Wix support directly.

**Cited nodes**

- `n46` (articles/ › Other/ › About Fast Checkout): # About Fast Checkout  Important:  This article is relevant for Wix Stores, Wix Bookings, and Wix Restaurants Orders (New).  Increase sales by making it easier for repeat customers to complete a purchase without re-entering their details. Using the Members Area, your customers can create an account on your site and save their details.  ## How fast checkout works  With a Members Area added to your 
- `n17418` (articles/ › Wix Stores/ › Wix Stores: Enabling Guest Checkout for PayPal): # Wix Stores: Enabling Guest Checkout for PayPal  Guest checkout for PayPal allows your customers to pay via PayPal without having a PayPal account. You can set up guest checkout for Standard or Fast Checkout.  Note:  Customers with PayPal accounts can still log in to their PayPal accounts to check out.  ## To enable guest checkout in PayPal:  - Sign in to your PayPal account.  - Click the Setting

### wixqa_expertwritten-0120

- Haiku verifier: **unsupported**
- Sonnet verifier: **supported**

**Question**

I would like to know how to change my payment provider for my Wix site after funds have been sent for an order.

**Reference answer**

1. Go to [Accept Payments] (https://users.wix.com/signin?originUrl=https%3A%2F%2Fwww.wix.com%2Fmy-account%2Fsite-selector%3FbuttonText%3DSet+Up+Payments%26title%3DSelect+a+Site%26autoSelectOnSingleSite%3Dtrue%26actionUrl%3Dhttps%3A%2F%2Fwww.wix.com%2Fdashboard%2F%7B%7BmetaSiteId%7D%7D%2Fpayments%2F&postLogin=https%3A%2F%2Fwww.wix.com%2Fmy-account%2Fsite-selector%3FbuttonText%3DSet%2BUp%2BPayments%26title%3DSelect%2Ba%2BSite%26autoSelectOnSingleSite%3Dtrue%26actionUrl%3Dhttps%253A%252F%252Fwww.wix.com%252Fdashboard%252F%257B%257BmetaSiteId%257D%257D%252Fpayments%252F&overrideLocale=en&forceRender=true) on your site's dashboard. 
  Tip: Check your business location at the top right. If incorrect, click the drop-down menu to change it.
  2. Click Connect next to Wix Payments, or click See More Payment Options.
  3. Click See Options beside Third-Party Credit / Debit Card Providers (if you don't see your preferred provider).
  4. Click Connect beside the provider you want to change to.
  5. Click Yes, Switch to confirm your new provider.
  6. Connect your account:
  - Have an account: Click Connect Existing Account and follow the steps to connect your account.
  - Don't have an account: Click Create an Account and follow the steps to create your account.
  
  If you are using Wix Hotels, please click on the link to learn how to set up and manage payments: [Wix Hotels] (https://support.wix.com/en/article/setting-up-your-payment-method-in-wix-hotels)

**Phase-A answer**

I couldn't find a Wix help article that covers changing your payment provider after funds have already been sent for an order, so I can't tell you how Wix handles those already-sent funds.

The closest documented steps are for switching accounts:

- **Switch to a different account with the same provider:** Go to Accept Payments on your site's dashboard, click Manage next to the provider, and then:
  - PayPal: enter the email of the account you want in Account information, then click Save.
  - Stripe: click Change account, enter your Stripe credentials, and click Continue.
  - Other providers: enter the new account's credentials in Account information, then click Save.
- **Check your current provider:** Use the same Manage option and view the credentials under Account information.
- **Switch to a different provider:** The docs say you can switch, for example to Wix Payments, if your site is already connected to another provider.
- **Active subscriptions:** If customers already bought plans, you must first cancel all active subscriptions, switch providers, and then ask customers to repurchase the subscription.

For what happens to payments already processed, the docs only describe transaction statuses (Pending, Successful, Paid Out, and so on) and reserve funds. To confirm how an already-sent payment is handled, contact Wix support.

**Cited nodes**

- `n6112` (articles/ › Other/ › Using a Different Account with the Same Payment Provider): # Using a Different Account with the Same Payment Provider  If you have more than one account with a third-party payment provider, you can switch to your preferred account to accept payments on your Wix site.  Additionally, Wix automatically connects you to the most suitable payment provider available in your region by creating a deferred account for you (e.g. with Stripe or PayPal). If you wish, 
- `n12071` (articles/ › Wix Payments/ › Wix Payments: Adding iDeal as a Payment Method › FAQs › I currently accept iDeal payments through another payment provider. Can I change to accept iDeal payments through Wix Payments?): #### I currently accept iDeal payments through another payment provider. Can I change to accept iDeal payments through Wix Payments?  Yes. You can switch to Wix Payments if you've already connected your Wix site to a different provider.
- `n17867` (articles/ › Wix Stores/ › Wix Stores: Selling Product Subscriptions › FAQs › How can I change payment providers if customers have already purchased plans?): #### How can I change payment providers if customers have already purchased plans?  If you choose to switch payment providers, you must first cancel all active subscriptions, switch providers, and then ask your clients to repurchase the same product subscription.

### wixqa_expertwritten-0124

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

I need to know how to reinstall the blog app to improve the loading issue on Wix.

**Reference answer**

To reinstall the Wix Blog app to address loading issues, you can follow these steps:

1. **Remove the Existing Blog App:**
   - Go to your Wix Editor.
   - In the Pages menu, locate the Blog page and the Post page.
   - If these pages are not visible, you may need to delete the existing blog setup. You can find instructions on how to delete the Wix Blog [here](https://support.wix.com/en/article/wix-blog-deleting-your-blog).

2. **Reinstall the Blog App:**
   - Go to the Wix App Market from your editor or directly from the Wix App Market website.
   - Search for 'Wix Blog' in the search bar.
   - Select the Wix Blog app from the search results and click 'Add to Site'.
   - Follow the prompts to complete the installation.

3. **Check for Loading Issues:**
   - Ensure your Wix app is updated to the latest version by checking the Apple App Store or Google Play.
   - Make sure your device supports the Wix app (iOS 11 and above for iPhone, Android 6.0 and above for Android).
   - If issues persist, try logging out and back into the Wix app, or clear the cache on your device.

**Phase-A answer**

I couldn't find documentation on reinstalling the Wix Blog app to fix loading issues, so I can't give you verified steps for that.

What the docs do cover:
- **Deleting an app:** Full-page apps are removed from Manage Apps in your site's dashboard. Editor element apps are removed by clicking the app in the Editor and pressing Delete. Dashboard apps are removed from Manage Apps and then their own deletion steps are followed (n555). The docs don't say which category the Blog app falls into.
- **Re-adding an app:** For Wix Portfolio, the docs say your content stays in the dashboard after deletion and reappears when you re-add the app, but design changes you made to the pages are lost (n28796). I don't know whether the Blog app behaves the same way, so back up your posts and design before removing it.

For the loading problem itself, the docs have a general note that large images slow down a blog, and that optimized image sizes help load times (n14428). Resizing your images may be a lower-risk first step than reinstalling. Wix support would be the best place to confirm whether reinstalling the Blog app is the right fix.

**Cited nodes**

- `n555` (articles/ › Other/ › Adding an App to Your Site › FAQs › How do I delete an app from my site?): #### How do I delete an app from my site?  There are different types of apps in the Wix App Market. Some are full-page apps which appear in the Editor. Others are Editor elements or simply dashboard tabs. Depending on the type of app, you need to delete differently.  - Full-page apps: Delete the app from Manage Apps.  - Editor element apps: Click the app in your Editor press Delete on your keyboar
- `n28796` (articles/ › Wix Portfolio/ › Wix Portfolio: Managing Your Wix Portfolio › FAQs › Will deleting the portfolio app remove projects and collections from my site?): #### Will deleting the portfolio app remove projects and collections from my site?  No. If you delete the Wix Portfolio app from your editor, your projects and collections still exist in the dashboard. If you re-add the app, your projects and collections will be visible again.  However, any design changes you made to the portfolio pages will be deleted when you remove the app. You will need to mak

### wixqa_expertwritten-0126

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

How can I rename web links?

**Reference answer**

To change your page URL:
1. [Go to your editor](https://manage.wix.com/account/site-selector/?actionUrl=https%3A%2F%2Fwww.wix.com%2Feditor%2F%7BmetaSiteId%7D%3FeditorSessionId%3D%7Besi%7D%26).
2. Click Pages & Menu on the left side of the editor.
3. Hover over the relevant page and click the More Actions icon .
4. Click SEO Basics.
5. Enter the page URL under URL slug (last part of the page's URL).
6. Press Enter on your keyboard.

**Phase-A answer**

The docs I searched don't have a section on renaming a web link. The only rename instruction I found is for menu items in the Login Bar: double-click the menu item and type a new name. Renaming a link inside a menu, as opposed to changing its URL, is the closest match (Login Bar menu, n10157).

To change where a link points, select the element and choose Web Address (or Link) again, then enter the new URL and click Done (n7270, n25993).

**Cited nodes**

- `n10157` (articles/ › Site Members/ › Site Members: Customizing the Login Bar and Menu › Managing the Login Bar Menu): ## Managing the Login Bar Menu  When logged-in members click the login bar, a drop-down menu opens. The Login Bar Menu is fully customizable and completely independent from the Member Menu. Choose which member tabs and pages you want this menu to show.  Tip:  While you can only show tabs in the Member Menu, the Login Bar Menu can link anywhere, including your private member pages.  Wix Editor  Stu

### wixqa_expertwritten-0148

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

I want to know how to transfer the edited page from the copy version to my original site without overwriting the original page.

**Reference answer**

Copy and paste pages as needed between your sites, as long as both are in the Wix Editor. When pasting a page on the target site, you can choose whether to apply the site's colors and fonts or keep the original design. Note:
You can only copy regular pages. You cannot copy:
Anchors, links, folders, lightboxes or router pages
Pages from third-party and Wix business solution apps (e.g. Wix Stores, Wix Bookings, Wix Restaurants etc).

To copy and paste a page:
Click Menus & Pages  on the left side of the Editor.
Right-click the relevant page and click Copy.
Open the Editor of the site you want to paste to.
Paste the page by doing one of the following:
Right-click anywhere on the screen and select Paste.
Right-click anywhere on the screen and select Paste & Apply Site Theme to apply the color and text themes on the target site.
(In the Pages panel) Rename the new page:
Enter the new page name.
Click Done

**Phase-A answer**

The docs I searched don't have a procedure for moving a single edited page from a site copy back to the original site, so I can't give you exact steps.

What the docs do cover:

- **Copy and paste elements between pages:** You can copy elements from one page or section and paste them onto another page of the same site (n9607). Pasting onto the original page adds to it and doesn't replace the whole page. You could copy the edited elements from the duplicate and paste them into the original page.
- **Duplicating a site:** Changes you make to a duplicate don't affect the live site (n3828). This means you have to bring the edits across yourself. The docs don't describe a way to merge a copy back into the original.
- **Sync (copy/overwrite):** Sync moves items between a sandbox collection and the live version of a collection (n18976). It applies to CMS collections, not to site pages, and it can overwrite content, so check it carefully before using it.
- **Store pages:** Wix Stores doesn't currently let you copy and paste store pages (n32376).

If you need the exact steps, contact Wix Support and ask whether a page can be exported or moved from a duplicated site to the original.

**Cited nodes**

- `n9607` (articles/ › Wix Editor/ › Wix Editor: Working with Elements › Copying and pasting elements): ## Copying and pasting elements  Copy and paste single or multiple elements to quickly build your content. You can copy elements from one page / section, and paste them on another to keep your site's design consistent.
- `n3828` (articles/ › Other/ › Duplicating Your Site): # Duplicating Your Site  Make a copy of your site so you have a safe space to experiment with different site pages and design elements. Any changes you make to the copy do not affect your live site. You can also transfer the duplicate to another account.  Click to duplicate your site  Duplicate your site  ## Duplicating your site  Learn how to duplicate your site from your editor or dashboard.  Da
- `n18976` (articles/ › CMS/ › CMS: Index of Terms › Sync (copy/overwrite)): ## Sync (copy/overwrite)  Sync allows you to move your content between your optional sandbox and live collections. You can copy selected or all items in a collection from a sandbox collection to the live version of that collection.  You can also overwrite a sandbox collection with all the content from the live version, or overwrite all your sandbox collections with the content from their live vers
- `n32376` (feature-requests/ › Wix Stores/ › Wix Stores Request: Duplicating Store Pages): # Wix Stores Request: Duplicating Store Pages  Currently, it is not possible to copy and paste store pages in order to duplicate them.  We are always working to update and improve our products, and your feedback is greatly appreciated.

### wixqa_expertwritten-0149

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

Im experiencing an issue with my image on the website. When I try to resize it, the image gets cut off and then multiplies.

**Reference answer**

If you are experiencing issues with your images on your site, please follow the steps below:
1. Make sure that the files you are uploading meet the requirements. Click [here](https://support.wix.com/en/article/wix-media-supported-media-file-types-and-file-sizes) for guidelines.
2. Try viewing your site on another device to see if the image issue occurs there as well.
3. Click any ""?"" inside the editor and type your problem. You might find the answer you are looking for.
4. Follow our general interactive tutorial [here](https://support.wix.com/en/article/wix-technical-assistant).

**Phase-A answer**

I couldn't find anything in the Wix help docs about an image that gets cut off and then multiplies when resized, so I can't confirm the cause. The docs do cover related behavior:

- **Cut-off images:** Galleries have a "When they're resized" setting. **Autocrop** crops images to fill the gallery frame, which cuts off parts of the image. **Fit** shows the whole image. You can change this in the gallery's Settings. (n8016)
- **Crop and resize:** Images have two resize options, Crop and Fit. (n17932) To crop, click the image, click the Crop icon, drag the handles, and click Apply. Resizing by dragging the handles also works. (n24080) To crop to a ratio, use Settings > Adjust > Crop & Resize > Crop ratio. (n8368)
- **Repeated images:** The docs don't describe images duplicating when resized. Duplicating is a deliberate action (the Duplicate icon on an element), and the docs don't mention it happening on its own.

To help narrow it down, tell me:
1. Is this in a gallery, a Post List, a background, or a standalone image?
2. Does it happen in the Editor, in Preview, or only on the live site?
3. Does the duplicate appear in the Editor's layers, or only visually on the page?

If it's a gallery, switching the resize setting from Autocrop to Fit is the first thing to try. If the problem continues, contact Wix Support with those details.

**Cited nodes**

- `n8016` (articles/ › Wix Editor/ › Wix Editor: Adjusting Your Gallery Settings › To change how images are resized:): ## To change how images are resized:  - Go to your editor.  - Click the gallery.  - Click the Settings icon .  - Select an option under When they're resized:  - Autocrop: Crops (cuts) the images to fill the entire gallery frame.  - Fit: Displays whole images in the gallery.  Tip:  You can crop your images further if resizing is not enough.
- `n17932` (articles/ › Wix Stores/ › Wix Stores: Setting How Store Images Are Displayed › Understanding image resizing): ## Understanding image resizing  Where images are displayed, you'll see two resizing options: Crop and Fit.
- `n8368` (articles/ › Wix Editor/ › Wix Editor: Cropping an Image › To crop an image using ratios:): ## To crop an image using ratios:  - Click the image in the Editor.  - Click the Settings icon .  - Click Adjust.  - Click Crop & Resize on the left side.  - Click Crop ratio.  - Select a ratio to crop the image.  - When you are finished, click the checkmark and click Save.
- `n24080` (articles/ › Site Performance/ › Site Performance: Best Practices › Optimizing your mobile site content › Crop or resize images): #### Crop or resize images  Large images may take a while to load on your mobile-friendly site. We recommend cropping or making your image smaller to prevent your mobile site's loading time being impacted.  To crop an image:  - Click the image in the Editor.  - Click the Crop icon .  - Drag the handles to crop the image.  - Click Apply.  Tip: Images can be resized by clicking the image, then dragg

### wixqa_expertwritten-0151

- Haiku verifier: **supported**
- Sonnet verifier: **unsupported**

**Question**

Im having trouble adding a page to the horizontal menu on my website.

**Reference answer**

To add a new page to your horizontal menu in the Wix Editor, follow these steps:

1. Go to your editor: [Wix Editor](https://manage.wix.com/account/site-selector/?actionUrl=https%3A%2F%2Fwww.wix.com%2Feditor%2F%7BmetaSiteId%7D%3FeditorSessionId%3D%7Besi%7D%26).
2. Click **Pages & Menu** on the left side of the editor.
3. Click **Add Page** at the top of the panel.
4. Choose the page template from the options.
5. Enter the new page name.
6. Click **Done**.

**Phase-A answer**

I couldn't find documentation that directly explains why a page isn't appearing in a horizontal menu, so I can't diagnose your specific issue. Here's what the docs do cover:

**Wix Editor (classic):**
1. Click **Add Elements** on the left side of the editor.
2. Click **Menu & Anchor**, then **Horizontal Menus**.
3. Drag a menu onto your page.

**Editor X (Styled Horizontal Menu):**
1. Click **Add** at the top of the editor, then **Menu & Search**, then **Styled Horizontal Menus**.
2. Drag the menu to where you want it.
3. To use custom pages, click **Manage Menu**, open the **Which menu is displayed?** drop-down, click **Manage Site Menus**, and click **+ Add New Menu**.

**Visibility tip:** The docs say a menu should appear on every page. If it's in the header or footer, it shows on all pages automatically. If it's a horizontal menu placed elsewhere on the page, or a vertical menu, set it to show on all pages.

If the page is still missing, check whether the menu you're editing is the one that's displayed on your site, and confirm the page is included in that menu. If you tell me which editor you use (Wix Editor or Editor X) and what happens when you try to add the page, I can search more specifically.

**Cited nodes**

- `n7623` (articles/ › Wix Editor/ › Wix Editor: Adding and Setting Up a Horizontal Menu › To add a horizontal menu:): ## To add a horizontal menu:  - Click Add on the left side of the Editor.  - Click Menu & Anchor.  - Click Horizontal Menus.  - Drag a menu onto your page.
- `n7359` (articles/ › Wix Editor/ › Wix Editor: Adding a Site Menu › To add a site menu:): ## To add a site menu:  - Go to your editor.  - Click Add Elements on the left side of the editor.  - Click Menu & Anchor.  - Click a menu type:  - My Menus: If you've already added menus to your site, the styles you've chosen appear in this section so you can use them again.  - Themed Menus: These menus have been handpicked to match your site.  - Horizontal Menus: A horizontal menu is usually pla
- `n20902` (articles/ › Editor X/ › Editor X: Using Styled Horizontal Menus › To add a Styled Horizontal Menu:): ## To add a Styled Horizontal Menu:  - Click Add at the top of Editor X.  - Click Menu & Search.  - Click Styled Horizontal Menus.  - Drag and drop the relevant menu to the desired location on your page.  - (Optional) Create a new menu with custom pages:  - Click Manage Menu.  - Click the drop-down under Which menu is displayed?.  - Click Manage Site Menus.  - Click + Add New Menu at the bottom to

### wixqa_expertwritten-0152

- Haiku verifier: **unsupported**
- Sonnet verifier: **unsupported**

**Question**

I want to change the preview picture that shows when using my URL.

**Reference answer**

To change the preview picture that shows when using your URL, follow these steps:

1. Open [your site's settings](https://www.wix.com/my-account/site-selector/?buttonText=Edit%20Site%20Info&title=Select%20a%20Site&autoSelectOnSingleSite=true&actionUrl=https://www.wix.com/dashboard/{{metaSiteId}}/settings/).
2. Click **Website settings**.
3. Scroll down to General social image and click **Upload Image**.
4. Select an image or click **\+ Upload Media** to upload a new one.
5. Click **Choose File** to add it.
6. Click **Save** at the top of the dashboard.
7. [Publish your site](https://support.wix.com/en/article/wix-editor-saving-previewing-and-publishing-your-site#publishing-your-site).

If you want to change the og:image for an individual page:

1. Click **Pages & Menu** on the left Editor menu.
2. Click the relevant page.
3. Click More Actions.
4. Select **Social share**.
5. Click **Upload Image**.
6. Select an image or click **\+ Upload Media** to upload a new one.
7. Click **Add to Page**.
8. [Publish your site](https://support.wix.com/en/article/wix-editor-saving-previewing-and-publishing-your-site#publishing-your-site).

**Phase-A answer**

The preview picture is the social share image (og:image). It's the image that appears next to your page's title and description when someone shares your URL on social networks.

To change it:
1. In your site's dashboard, go to **Search Engine Optimization (SEO)**.
2. Scroll down to **Tools and settings**, then click **Go to SEO Settings** under SEO Settings.
3. Select the page type you want to edit.
4. Click **Edit** next to **Basics & social share**.
5. Scroll down to **Social share** and set **og:image**. You can enter an image URL to use one image for all pages, or use variables to show a different image on each page.
6. To get an image URL, click **Get an Image URL from Site Files**, hover over an image, click the More Actions icon, and select **Copy URL**.
7. Click **Save**.

If the old image still shows after you save, the platform may have cached it. For Telegram, you can use Telegram's Webpage Bot to refresh the preview. For Facebook, blog post cover images control the image shown when a blog post is shared.

Sources: n3464, n3465, n3463, n6042, n8186

**Cited nodes**

- `n3464` (articles/ › Other/ › Customizing the Social Share Settings for Your Site's Pages › To customize a page's Social Share settings:): ## To customize a page's Social Share settings:  - Go to Search Engine Optimization (SEO) in your site's dashboard.  - Scroll down to Tools and settings.  - Click Go to SEO Settings under SEO Settings.  - Select the page type that you want to edit. Note: You will only see options for the pages that are part of your site. For example, if you added Wix Stores to your site, you'll see an option to cu
- `n3465` (articles/ › Other/ › Customizing the Social Share Settings for Your Site's Pages › To customize a page's Social Share settings: › Social share): #### Social share  You can use static text to apply the same title and description to every page, or use variables to create rules to use different values for each section or page of your site.  By default, the title tag and meta description from your SEO Basics section are used in this section as variables:  - og:title: The Title tag from the SEO Basics section.  - og:description: The Meta descri
- `n3463` (articles/ › Other/ › Customizing the Social Share Settings for Your Site's Pages › Customizing Your Page's Social Share Settings): ## Customizing Your Page's Social Share Settings  Go to the Social Share section in your SEO Settings to customize your page's Social Share settings.

### wixqa_expertwritten-0167

- Haiku verifier: **unsupported**
- Sonnet verifier: **supported**

**Question**

Im experiencing unwanted gaps at the bottom of my page when I publish it on the desktop version using the Wix Editor.

**Reference answer**

If your dynamic item page has a large space or gap at the bottom, it's usually because item pages are different lengths, and the layout was not edited in the shortest item page. To prevent this, design according to the shortest item, in its respective item page, and use strips instead of placing elements "freely" inside the sections.
How to fix it?
Design your pages according to the shortest item. This ensures that all pages maintain a consistent layout. Also, use [strips](https://support.wix.com/en/article/wix-editor-adding-and-setting-up-a-strip) to attach elements inside the sections. This makes your design more responsive and avoids large spaces or gaps.

**Phase-A answer**

The docs I found don't have a specific fix for desktop gaps in the Wix Editor. Most of the gap articles cover the mobile site, which is a different problem. The closest match is an Editor X article, so check whether your site is on Editor X or the Wix Editor before trying its steps.

If the article applies to your site, these are the likely causes:

1. **Elements outside the section:** Open Layers, click each element, and make sure it sits inside the section. Move or resize any element that extends past the edge.
2. **Elements crossing the page edge:** Hover over elements near the left and right edges and move or resize any that overflow. Text elements often cause this.
3. **Overflow setting:** Select the page in Layers, open the Inspector, go to the Layout tab, and set Overflow content to Hide. This crops anything that spills past the page edges.
4. **Section height:** Select the section, open the Inspector, go to Layout, and check the Height and Min H values under Size. A large height or minimum height, especially one set in vh, can leave a gap at the bottom.

If none of these fixes it, contact Wix support.

Source: "Editor X: Troubleshooting Unwanted Gaps and Horizontal Scroll Bars" (n20758).

**Cited nodes**

- `n20758` (articles/ › Editor X/ › Editor X: Troubleshooting Unwanted Gaps and Horizontal Scroll Bars): # Editor X: Troubleshooting Unwanted Gaps and Horizontal Scroll Bars  Noticed a blank space on your page, or a horizontal scroll bar that wasn't intentional? In this article, learn what you should check to make sure they don't appear to visitors on any screen size.  ## Step 1 | Find elements to re-position in the Layers panel  Open the Layers panel to see all the elements of your page in an organi

### wixqa_expertwritten-0182

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

How users can check my calendar on the website?

**Reference answer**

It is possible to add a calendar to your site. This will allow visitors to discover upcoming events in an interactive and engaging way. There are a range of options available to suit your site's needs. 
  To add a calendar:
  Click Add Apps on the left side of the Editor.
  Type "Calendar" in the search field and press Enter.
  Scroll through the available calendar apps. Note: The Google Event Calendar and Wix Bookings apps are created by Wix.
  Select the app you want to add.
  Click Add to Site.
  Click the app in the Editor.
  Click Settings to set up the app.

**Phase-A answer**

The docs don't describe a general way for visitors to view your personal calendar. What they do cover is the Wix Bookings calendar page, where clients can see your service availability.

- **Calendar Page:** Clients view the availability of your services and select the time slots they want to book there. You can customize its design and text in the Editor. (n10348)
- **Next Availability widget:** You can show the next open time slot for a service directly on your website, so clients can book without searching a calendar or contacting you. (n10841)

If you meant a different calendar, such as an events calendar app, the docs mention third-party apps (for example, Boom Event Calendar or Events Calendar by inlight labs) that display events on your site. I didn't read those in detail.

**Cited nodes**

- `n10348` (articles/ › Wix Bookings/ › Wix Bookings: About Bookings Pages › Display your service times on the Calendar Page): ## Display your service times on the Calendar Page  The Calendar Page is where clients view the availability of your services and select the time slots they want to book. Ensure the information is as clear as possible to make it easy for your clients to book sessions with you.  You can customize the design and edit the text for your calendar page in the Editor.
- `n10841` (articles/ › Wix Bookings/ › Wix Bookings: Adding and Setting Up the Next Availability Widget): # Wix Bookings: Adding and Setting Up the Next Availability Widget  The Next Availability widget helps streamline the booking process for your clients. With this widget, you can display the next available time slot for a specific service directly on your website. Clients can then book appointments without having to search through a calendar or contact you directly.  ## Step 1 | Add the Next Availa

### wixqa_expertwritten-0197

- Haiku verifier: **unsupported**
- Sonnet verifier: **supported**

**Question**

Im having a glitch on my site where the text on one of my menu items wont update.

**Reference answer**

To rename a menu item in an advanced menu:

Click the advanced menu in your editor.
Cick Manage Menu.
Click the More Actions icon  next to the relevant item.
Click Rename / Rename page.
Enter the new name into the field.
Click Done.

**Phase-A answer**

I couldn't find a doc that describes this exact problem, so these are general steps from the help center, not a confirmed fix:

1. **Publish again.** Click Publish in the Editor. The docs say the cache is cleared every time you publish (n24094).
2. **Refresh the live site.** Hard-refresh or reload the live page after publishing (n9067).
3. **Clear your browser cache.** If the old text still shows, clear the browser cache and try again (n6615).

If it still doesn't update, check that you edited the menu item itself. Labels and item names are changed in Menus (New) by clicking the Edit icon next to the item (n23911). If the problem persists after these steps, contact Wix support with a screenshot of the menu and the live page.

**Cited nodes**

- `n24094` (articles/ › Site Performance/ › Site Performance: Caching Pages to Optimize Loading Speed › FAQs › When is cache cleared?): #### When is cache cleared?  Cache is cleared up to every week (automatically) or up to every time period you specify manually. It’s also cleared every time you click Publish in the Editor.  Note: If you enable cache rendering for a page, make changes, and revert your site back to that version, it is still enabled.
- `n9067` (articles/ › Wix Editor/ › Wix Editor: Menu Issues › To resolve issues with your site's menu click below: › Menu missing on live site): #### Menu missing on live site  If you cannot view your menu on your live site, try the following:  - Make sure you've added a menu to your site. Learn How  - If your menu is attached to the header or footer, or set to "show on all pages," make sure you are not hiding the header and footer:  - Click Menus & Pages on the left side of the Editor.  - Click the relevant page that isn't displaying your
- `n6615` (articles/ › Other/ › Wix Technical Assistant › Troubleshooting technical issues manually › 2. Clear your cache): #### 2. Clear your cache  Local issues can often be resolved by clearing your browser's cache. If the issue is not resolved, try disabling your browser's add-ons and extensions (see below).

### wixqa_expertwritten-0199

- Haiku verifier: **supported**
- Sonnet verifier: **supported**

**Question**

Im trying to remove a menu from the header of my Wix site.

**Reference answer**

To delete an element from your site:

Open the Editor.
Click the relevant element to select it.
Choose how you want to delete the element:
Keyboard: Press Delete on your keyboard.
Right-click menu: Right-click the element, then click Delete.

**Phase-A answer**

The docs don't say how to delete a menu from the header specifically, but they do cover the closest options:

- **Hide it:** In the header editor, click the icon next to the content section (such as the menu) to show or hide it. (n14621)
- **Remove the header entirely:** Not possible. The docs say you can hide sections of the header but not remove the header itself. (n14621)
- **Move a menu element out:** If the menu is an element inside the header, drag it out of the header into another area of the page. Once it's outside the header or footer, it no longer appears on all pages. (n9116)

If you need the menu gone from every page, hiding the section from the header is the most direct route. The docs don't give exact click paths for this, so check the header editor for the icon next to the menu.

**Cited nodes**

- `n14621` (articles/ › ADI/ › ADI: About Your Site Header and Footer › Editing your header content): ## Editing your header content  Your header appears at the top of every page of your site. It usually contains your business name, logo, and site menu. You can update the header content, add social links, and show or hide content sections by clicking the icon next to them.  Important:  While you can hide content sections in your header, it is not possible to remove the header from your site comple
- `n9116` (articles/ › Wix Editor/ › Wix Editor: Placing Elements in Your Header, Footer and Page › FAQs › How do I remove an element from my header or footer?): #### How do I remove an element from my header or footer?  Just drag and drop the element away from the header or footer and into another area of your page.  Once you remove an element from the header or footer, it is no longer displayed on all pages. Learn how to set the element to show on all pages
- `n7952` (articles/ › Wix Editor/ › Wix Editor: Customizing the Header and Footer on Your Mobile Site › Adding or removing the header and footer): ## Adding or removing the header and footer  Add or remove the header and footer elements at any time. For regular pages, we recommend keeping your header and footer visible, so visitors can easily explore and navigate your site.
