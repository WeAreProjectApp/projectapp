import { LEGAL_ENTITY as L } from '../../config/legalEntity.js'

// Courtesy English translation of locales/waiter/es.js. The Spanish copy is
// the official text; keep both files structurally identical.
// Inline markup rendered by components/legal/LegalRichText.vue:
// **bold**, `code` and [label](href).

const MAIL = `[${L.email}](mailto:${L.email})`
const PHONE = `[${L.phone}](${L.phoneHref})`
const ADDRESS = `${L.address}, ${L.city}, ${L.country}`
const HOURS = 'Monday to Friday, 8:00 a.m. to 6:00 p.m., Colombia time'
const UPDATED = 'Last updated: October 7, 2026.'
const TRANSLATION_NOTICE = 'This is a courtesy translation. The Spanish version is the official text and prevails in case of conflict.'

export default {
  footer: {
    nav_label: 'Waiter legal pages',
    product: 'Waiter',
    privacy: 'Waiter privacy policy',
    terms: 'Waiter terms of service',
    data_deletion: 'Data deletion',
    contact: 'Contact',
    phone_label: 'Phone',
    copyright: '© 2026 ProjectApp. Waiter is a ProjectApp product.',
  },

  company: {
    title: 'Company details',
    legal_name: 'Trade name',
    owner: 'Owner',
    nit: 'Tax ID (NIT)',
    address: 'Address',
    phone: 'Phone and WhatsApp',
    email: 'Sales, support and privacy',
    hours: 'Business hours',
    hours_value: 'Monday to Friday, 8:00 a.m. to 6:00 p.m., Colombia time',
  },

  back_to_waiter: 'Back to Waiter',
  back_to_home: 'Back to home',

  product: {
    eyebrow: 'A ProjectApp product',
    title: 'Waiter',
    tagline: 'The restaurant system that also serves customers on WhatsApp.',
    intro:
      'Waiter is ProjectApp’s point of sale for restaurants in Colombia: cash register, tables and floor plan, orders, kitchen display, inventory and recipes, reservations, customers and loyalty points, QR digital menu, online payments and reports.',
    cta_contact: 'Talk to us',
    cta_privacy: 'Privacy policy',
    features: [
      {
        title: 'The whole restaurant in one system',
        text: 'Cash register with opening and closing counts, floor plan, dine-in, takeaway and delivery orders, kitchen display, inventory with recipes, reservations with deposits, customers with points and rewards, invoicing, reports and an owner console covering every location.',
      },
      {
        title: 'Digital menu with an assistant',
        text: 'Guests scan the table QR code, browse the menu, order and pay from their phone. An AI assistant helps them choose and answers their questions about the dishes.',
      },
      {
        title: 'Customer service on WhatsApp',
        text: 'The restaurant connects its WhatsApp Business number to Waiter through Meta’s official signup, in a few minutes and without changing numbers. The assistant answers customers’ messages about the menu, opening hours and location; it builds the order, shows the total calculated by the system and sends it to the kitchen only after the customer confirms it. Staff can take over the conversation at any time.',
      },
    ],
    steps_title: 'How the WhatsApp connection works',
    steps: [
      'The owner opens their Waiter console and clicks “Connect WhatsApp”.',
      'They log in with their Meta account and authorize Waiter to send and receive messages on behalf of their business.',
      'They verify their number with the code sent by SMS or voice call.',
      'From then on, customer messages reach the Waiter assistant, and orders reach the point of sale.',
    ],
    steps_note:
      'The restaurant can disconnect its number at any time from the Waiter console or from its Meta account.',
    data_title: 'Your data and your customers’ data',
    data_text:
      'The restaurant owns its customers’ information; ProjectApp processes it only to provide the service. Read our [privacy policy](/waiter/privacy), the [terms of service](/waiter/terms) and [how to request deletion of your data](/waiter/data-deletion).',
  },

  privacy: {
    title: 'ProjectApp Personal Data Processing Policy',
    last_updated: UPDATED,
    notice: `${TRANSLATION_NOTICE} This policy applies to **Waiter** and its users. Use of the projectapp.co website and ProjectApp’s development services is also governed by the [website privacy policy](/privacy-policy).`,
    sections: [
      {
        id: 'who-we-are',
        title: '1. Who we are',
        blocks: [
          { p: `ProjectApp is the trade name of **${L.tradeName}**, a business owned by **${L.owner}**, identified with Colombian tax ID (NIT) ${L.nit} (national ID ${L.nationalId}), domiciled at ${ADDRESS}, phone ${PHONE} and email ${MAIL} (“ProjectApp”, “we”).` },
          { p: 'ProjectApp develops and operates **Waiter**, a cloud system for restaurants: point of sale, floor, kitchen, inventory, reservations, customers and points, QR digital menu, online payments, an AI assistant on the menu and on WhatsApp, invoicing and reports.' },
        ],
      },
      {
        id: 'our-role',
        title: '2. Our role regarding your data',
        blocks: [
          {
            ul: [
              '**When you are a customer of a restaurant that uses Waiter** (diner, person making a reservation or writing on WhatsApp), the **controller** of the processing is **that restaurant**: it decides which data it asks for and why. ProjectApp acts as **processor**: it processes your data on the restaurant’s behalf, only to provide the Waiter service and according to its instructions. To exercise your rights you may contact the restaurant or us, and we will forward your request.',
              '**When you are an employee of a restaurant** that uses Waiter, the controller is the restaurant, as your employer, and ProjectApp is the processor.',
              '**When you are the owner or representative of a restaurant that subscribes to Waiter, a member of the ProjectApp team or a visitor of projectapp.co**, ProjectApp is the **controller**.',
            ],
          },
        ],
      },
      {
        id: 'data-we-process',
        title: '3. Data we process',
        blocks: [
          { h3: '3.1 Restaurant customers (diners)' },
          {
            ul: [
              '**If you use the digital menu without signing up:** a random identifier stored in a cookie and, if you type it, your name or nickname.',
              {
                text: '**If you create an account on a restaurant’s menu:**',
                items: [
                  'name, email and, if you provide it, mobile number;',
                  'password, stored hashed with a one-way algorithm;',
                  'allergies or foods you avoid, if you write them down;',
                  'whether you agree to receive news, which comes unchecked;',
                  'the record that you accepted this policy;',
                  'favorite dishes, rewards and prizes, and the reviews and ratings you leave.',
                ],
              },
              {
                text: '**If the restaurant registers you as a customer:**',
                items: [
                  'name, phone, email;',
                  'ID type and number;',
                  'address and city;',
                  'points, rewards and their transaction history.',
                ],
              },
              {
                text: '**Orders:**',
                items: [
                  'what you order;',
                  'kitchen notes and the allergies you indicate;',
                  'the table;',
                  'for deliveries, address and phone;',
                  'tip, payments and refunds.',
                ],
              },
              {
                text: '**Reservations:**',
                items: [
                  'name, phone and email;',
                  'party size, date and time, notes;',
                  'deposit and its status.',
                ],
              },
              {
                text: '**Online payments:**',
                items: [
                  'the amount, payment method, status and transaction reference;',
                  'for cards, only the card network (Visa, Mastercard or American Express).',
                ],
              },
              {
                text: '**Electronic invoicing:** the buyer details you ask to include on the invoice:',
                items: [
                  'name or company name;',
                  'ID type and number;',
                  'email, address and city.',
                ],
              },
              '**Conversations with the assistant:** the messages you write in the menu chat or on WhatsApp, the assistant’s replies and the dishes it suggested.',
              {
                text: '**WhatsApp**, when the restaurant connects its number to Waiter:',
                items: [
                  'your WhatsApp number and profile name;',
                  'the content of the messages you send to the restaurant and those the restaurant or its assistant send you;',
                  'the date and time of each message and its status (sent, delivered, read).',
                ],
              },
            ],
          },
          { h3: '3.2 Restaurant staff' },
          {
            ul: [
              'Name, username, email, role and assigned locations.',
              'Shift schedule and clock-in/clock-out records, to calculate hours worked.',
              'Hourly rate, if the owner records it.',
              'Sales and tips from the orders they register.',
              'The actions they take in the system (change history).',
              'Password hashed with a one-way algorithm.',
            ],
          },
          { p: 'We do not store your location or your IP address when you sign in.' },
          { h3: '3.3 Restaurant owners and the ProjectApp team' },
          {
            ul: [
              'Company contact and billing details.',
              'Users and hashed passwords.',
              'Second authentication factor.',
              'Access logs and records of support actions.',
            ],
          },
          { h3: '3.4 Visitors of projectapp.co' },
          { ul: ['The data you send us through the form or by email.'] },
        ],
      },
      {
        id: 'data-we-do-not-process',
        title: '4. Data we do NOT process',
        blocks: [
          {
            ul: [
              '**We do not receive or store your card number.** You send it directly to the payment gateway (Wompi), which returns a token that cannot be used to charge you anywhere else.',
              'We do not use analytics or advertising tools to track you on the menu or at the point of sale.',
              'We do not sell or rent personal data.',
              'We do not use WhatsApp messages or conversations with the assistant for advertising or to train artificial intelligence models.',
              '**Your location is not sent to our servers.** If you allow it on the digital menu, it is used only on your phone to show the distance to the restaurant.',
            ],
          },
        ],
      },
      {
        id: 'purposes',
        title: '5. How we use the data',
        blocks: [
          {
            ul: [
              {
                text: 'Providing the Waiter service to the restaurant:',
                items: [
                  'taking, preparing, charging and delivering orders;',
                  'managing reservations, customers, points and rewards;',
                  'invoicing;',
                  'running the cash register and inventory;',
                  'generating reports.',
                ],
              },
              'Serving you on the digital menu and on WhatsApp with the assistant. The assistant answers questions about the menu, recommends dishes and builds orders that are sent to the kitchen only after you confirm them.',
              'Processing online payments and reservation deposits.',
              'Emailing you what you asked for: reservation confirmations, sales documents, password recovery codes.',
              'Sending you the restaurant’s news and promotions, **only if you agreed to it**. You can withdraw your consent at any time.',
              'Calculating staff hours, sales and tips as a basis for the restaurant’s payroll.',
              {
                text: 'Security:',
                items: [
                  'preventing unauthorized access and fraud;',
                  'limiting sign-in attempts;',
                  'keeping a record of who changed what.',
                ],
              },
              'Providing technical support to the restaurant. We only access the restaurant’s account with its express permission, for a limited time, and the access is logged.',
              'Complying with legal, accounting and tax obligations.',
            ],
          },
        ],
      },
      {
        id: 'artificial-intelligence',
        title: '6. Artificial intelligence',
        blocks: [
          { p: 'The Waiter assistant uses a language model from **OpenAI** to understand your message and propose a reply.' },
          { p: '**What we send to OpenAI:**' },
          {
            ul: [
              'the text you write;',
              'the latest messages of the conversation;',
              'the restaurant’s menu (dishes, descriptions, ingredients and prices).',
            ],
          },
          { p: '**What we do NOT send:** your name, email or phone. We ask OpenAI not to store the requests, and its terms for API customers state that it does not use this data to train its models.' },
          { p: '**That is why we ask you** not to write sensitive data in the chat that is not needed for your order. Put allergies in the allergies field of your order or account: that way they reach the kitchen.' },
          { p: '**Assistant limits:** it cannot charge, give discounts, change prices or confirm orders on its own. Prices and totals are calculated by the restaurant’s system.' },
        ],
      },
      {
        id: 'whatsapp',
        title: '7. WhatsApp',
        blocks: [
          { p: 'When a restaurant connects its WhatsApp Business number to Waiter, we use Meta’s official platform (WhatsApp Business Platform).' },
          { p: '**When you write to the restaurant, Meta provides us with:**' },
          { ul: ['your number;', 'your profile name;', 'your messages;', 'the delivery status of the messages.'] },
          { p: '**We use them only to:**' },
          {
            ul: [
              'let the restaurant and its assistant reply to you;',
              'record your orders and reservations;',
              'send you updates about them, for example “your order is ready”.',
            ],
          },
          { p: '**What we do not do:**' },
          {
            ul: [
              'we do not send you promotional WhatsApp messages without your consent;',
              'we do not share your number or messages with other restaurants.',
            ],
          },
          { p: '**You can write “humano” (human)** or ask to talk to a person at any time. You can also block the restaurant’s number to stop receiving messages.' },
          { p: 'Meta processes the data under its own policies, available at [whatsapp.com/legal](https://www.whatsapp.com/legal).' },
        ],
      },
      {
        id: 'sharing',
        title: '8. Who we share data with',
        blocks: [
          { p: 'Only with those we need to provide the service, under contracts that require them to protect it:' },
          {
            table: {
              head: ['Who', 'Purpose', 'Where'],
              rows: [
                ['The restaurant you use', 'It is the controller of your data: it prepares your order, serves you and invoices you', 'Colombia'],
                ['Meta Platforms (WhatsApp Business Platform)', 'Sending and receiving the restaurant’s WhatsApp messages', 'United States and other countries'],
                ['OpenAI', 'Language model for the assistant (see section 6)', 'United States'],
                ['Wompi (Bancolombia)', 'Processing online payments and deposits', 'Colombia'],
                ['Amazon Web Services (AWS)', 'Hosting Waiter and its databases', 'United States'],
                ['Google (Google Workspace)', 'Sending service emails', 'United States'],
                ['DIAN and the restaurant’s electronic invoicing provider', 'Validating electronic invoices, when the restaurant invoices', 'Colombia'],
                ['Google', 'Screen fonts and Google Maps “Directions” links (Google receives your IP address when loading them)', 'United States'],
                ['Authorities', 'When a law or court order requires it', 'Colombia'],
              ],
            },
          },
          { p: 'Some of these providers are outside Colombia. In those cases we make an **international transmission** to processors that must handle the data only according to our instructions and with equivalent security measures.' },
        ],
      },
      {
        id: 'retention',
        title: '9. How long we keep data',
        blocks: [
          {
            table: {
              head: ['Data', 'Period'],
              rows: [
                ['Diner account', 'Until you ask us to delete it or after 24 months without use'],
                ['Conversations with the assistant (menu and WhatsApp)', '90 days from the last message; you can delete the menu conversation at any time from the chat'],
                ['Orders, payments, sales documents and reservations', 'The period required by accounting and tax rules (up to 10 years); contact details not needed for that obligation are anonymized after 24 months'],
                ['Customers registered by the restaurant', 'While the restaurant is a Waiter customer and needs them, or until you request their deletion'],
                ['Restaurant staff', 'While the person works at the restaurant and up to 5 years afterwards, as payroll and hours records'],
                ['Change history and security logs', '2 years'],
                ['Session cookies', 'Up to 12 hours on the menu; until the end of the shift at the point of sale'],
                ['When a restaurant leaves Waiter', 'We hand over its data if requested and delete it after 90 days, except what the law requires us to keep'],
              ],
            },
          },
        ],
      },
      {
        id: 'rights',
        title: '10. Your rights',
        blocks: [
          { p: 'Under Colombian Law 1581 of 2012, you can:' },
          {
            ul: [
              '**access, update and correct** your data;',
              '**request proof** of the authorization you gave;',
              '**know how it has been used**;',
              '**revoke** the authorization and **request deletion**, when there is no legal or contractual duty to keep it;',
              '**access your data free of charge**;',
              '**file complaints** with the Superintendence of Industry and Commerce (SIC) after completing the process with us or with the restaurant.',
            ],
          },
          { p: `**How to exercise them:** write to ${MAIL} stating:` },
          {
            ul: [
              'your name;',
              'the restaurant;',
              'the contact detail you used with Waiter (email or WhatsApp number);',
              'what you are requesting.',
            ],
          },
          { p: 'If you are a restaurant customer, you can also ask the restaurant directly.' },
          { p: '**Response times:**' },
          {
            ul: [
              '**inquiries:** 10 business days, extendable by 5 more;',
              '**claims** (correction, update, deletion or revocation): 15 business days, extendable by 8 more.',
            ],
          },
          { p: 'We will let you know if we need the extension.' },
          { p: '**Data deletion:** the step-by-step guide is at [projectapp.co/waiter/data-deletion](/waiter/data-deletion).' },
        ],
      },
      {
        id: 'security',
        title: '11. Security',
        blocks: [
          {
            ul: [
              'Encrypted communication (HTTPS).',
              'Passwords stored with one-way algorithms, and codes and sessions stored as cryptographic hashes.',
              'Encrypted payment gateway credentials.',
              'Strict separation of each restaurant’s information.',
              'Mandatory second factor for the ProjectApp team.',
              'Support access only with the restaurant’s permission, time-limited and logged.',
            ],
          },
          { p: 'If an incident affects your data, we will inform the restaurant, the SIC and you when the law requires it.' },
        ],
      },
      {
        id: 'cookies',
        title: '12. Cookies and storage on your device',
        blocks: [
          { p: '**On the digital menu:**' },
          {
            ul: [
              'a **session cookie** (`waiter_diner`, up to 12 hours) that identifies you at the table;',
              'a cookie that remembers you already saw the restaurant’s introduction (1 year);',
              'in your browser, your menu preferences, which you can clear from the menu itself.',
            ],
          },
          { p: '**At the point of sale:**' },
          {
            ul: [
              'staff session cookies;',
              'on the restaurant’s device, a temporary copy of working information, to keep operating without internet.',
            ],
          },
          { p: 'Waiter does not use advertising or analytics cookies.' },
        ],
      },
      {
        id: 'minors',
        title: '13. Minors',
        blocks: [
          { p: 'Waiter is not directed at minors. If a minor uses a restaurant’s menu, they must do so with the authorization of their legal representative, and their data is processed respecting their best interests.' },
        ],
      },
      {
        id: 'changes',
        title: '14. Changes to this policy',
        blocks: [
          { p: 'If we change it, we will publish the new version here with its date. If the change is significant, we will notify restaurants and, where appropriate, you.' },
        ],
      },
      {
        id: 'contact',
        title: '15. Contact',
        blocks: [
          { p: `${MAIL} · ${PHONE} · ${ADDRESS}.` },
        ],
      },
    ],
  },

  terms: {
    title: 'Waiter Terms of Service',
    last_updated: UPDATED,
    notice: `${TRANSLATION_NOTICE} These terms summarize the contract with restaurants and the usage rules for the features their customers see. The commercial contract signed with each restaurant prevails.`,
    sections: [
      {
        id: 'service',
        title: '1. The service',
        blocks: [
          { p: `Waiter is cloud software by ProjectApp (${L.tradeName}, a business owned by ${L.owner}, NIT ${L.nit}) that restaurants subscribe to. It includes:` },
          {
            ul: [
              'point of sale, floor, kitchen, inventory, reservations;',
              'customers and points, invoicing, reports and the owner console;',
              'digital menu, online payments and the menu and WhatsApp assistant.',
            ],
          },
          { p: 'Available modules depend on the subscribed plan.' },
        ],
      },
      {
        id: 'accounts',
        title: '2. Accounts and security',
        blocks: [
          { p: 'The restaurant is responsible for:' },
          {
            ul: [
              'its staff accounts, keeping their passwords confidential and deactivating anyone who stops working with it;',
              'the accuracy of its menu, prices, taxes and tax details.',
            ],
          },
        ],
      },
      {
        id: 'acceptable-use',
        title: '3. Acceptable use',
        blocks: [
          { p: 'Waiter may not be used to:' },
          {
            ul: [
              'carry out illegal activities;',
              'send unsolicited or bulk messages (spam);',
              'impersonate others;',
              'breach the security of the service;',
              'process personal data without the authorization of its owners.',
            ],
          },
        ],
      },
      {
        id: 'whatsapp',
        title: '4. WhatsApp',
        blocks: [
          { p: 'By connecting its number, the restaurant:' },
          {
            ul: [
              'authorizes Waiter to send and receive WhatsApp messages on its behalf;',
              {
                text: 'agrees to comply with the [WhatsApp Business policies](https://business.whatsapp.com/policy), in particular:',
                items: [
                  'having its customers’ consent to receive messages;',
                  'using approved templates outside the customer service window;',
                  'honoring requests to stop receiving messages.',
                ],
              },
            ],
          },
          { p: '**Costs:** the fees Meta charges for messages are paid by the restaurant directly to Meta, unless the plan states otherwise.' },
          { p: '**Disconnection:** the restaurant can disconnect its number at any time.' },
        ],
      },
      {
        id: 'assistant',
        title: '5. AI assistant',
        blocks: [
          { p: 'The assistant proposes replies and orders based on the restaurant’s menu:' },
          {
            ul: [
              'it can make mistakes;',
              'it does not charge, give discounts or change prices;',
              'orders are sent to the kitchen only with the customer’s confirmation;',
              'prices and totals are calculated by the system.',
            ],
          },
          { p: 'The restaurant must review its menu information (ingredients and allergens) and have a person attend whenever the customer asks.' },
        ],
      },
      {
        id: 'data',
        title: '6. Data',
        blocks: [
          {
            ul: [
              'The restaurant is the controller of its customers’ and staff’s data; ProjectApp processes it as processor under the [privacy policy](/waiter/privacy).',
              'The restaurant can export its information and request its deletion when the service ends.',
            ],
          },
        ],
      },
      {
        id: 'payments',
        title: '7. Payments',
        blocks: [
          {
            ul: [
              'The subscription is billed monthly according to the current plan and price list.',
              'Usage-based consumption is charged on the following month’s bill (for example, WhatsApp assistant orders or menu assistant messages).',
              'Late payment may lead to suspension of the service, with prior notice.',
              'Payment gateway fees are charged by each gateway.',
            ],
          },
        ],
      },
      {
        id: 'availability',
        title: '8. Availability and support',
        blocks: [
          {
            ul: [
              'We make reasonable efforts to keep Waiter available.',
              'The point of sale keeps working offline for basic operations, and information syncs when the connection returns.',
              'Third-party outages (DIAN, Meta, payment gateways, internet providers) are beyond ProjectApp’s control.',
              `Support is provided by email (${MAIL}) and by phone and WhatsApp (${PHONE}), ${HOURS}.`,
            ],
          },
        ],
      },
      {
        id: 'liability',
        title: '9. Liability',
        blocks: [
          { p: 'ProjectApp is liable for the diligent provision of the service, up to the amount paid by the restaurant in the 3 months before the event, except in cases of willful misconduct or gross negligence. It is not liable for the restaurant’s decisions, information uploaded by it, or third-party failures.' },
        ],
      },
      {
        id: 'termination',
        title: '10. Termination',
        blocks: [
          { p: 'The restaurant can cancel with 30 days’ notice. ProjectApp can suspend or terminate the service for breach of these terms or late payment.' },
        ],
      },
      {
        id: 'law-and-contact',
        title: '11. Governing law and contact',
        blocks: [
          { p: 'These terms are governed by the laws of Colombia.' },
          { p: `Contact: ${MAIL} · ${PHONE}.` },
        ],
      },
    ],
  },

  data_deletion: {
    title: 'How to request deletion of your data',
    last_updated: UPDATED,
    notice: TRANSLATION_NOTICE,
    sections: [
      {
        id: 'diners',
        title: 'If you used Waiter as a restaurant customer',
        blocks: [
          { p: 'This applies if you used the digital menu, made reservations or wrote to a restaurant on WhatsApp.' },
          {
            ol: [
              `Write to ${MAIL} with the subject **“Eliminar mis datos”** (delete my data).`,
              {
                text: 'Include:',
                items: [
                  'the restaurant’s name;',
                  'the email or WhatsApp number you used with it;',
                  'whether you want everything deleted or only part of it, for example the conversation with the assistant.',
                ],
              },
              'We will ask you to confirm your identity with a code sent to that same email or number.',
              {
                text: 'Within **15 business days** at most, we delete or anonymize:',
                items: [
                  'your menu account;',
                  'your conversations with the assistant and on WhatsApp;',
                  'your contact details in the restaurant’s customer records;',
                  'your favorites and preferences.',
                ],
              },
              'We send you a confirmation with a request code.',
            ],
          },
          { p: '**What we keep by legal obligation:** the orders, payments and invoices the law requires us to keep, without your name or contact details whenever possible.' },
        ],
      },
      {
        id: 'whatsapp',
        title: 'If you stopped writing to a restaurant on WhatsApp',
        blocks: [
          {
            ul: [
              'you can block its number on WhatsApp to stop receiving messages;',
              'to erase what you already sent, follow the steps above.',
            ],
          },
        ],
      },
      {
        id: 'restaurants',
        title: 'If you are a restaurant',
        blocks: [
          { p: `You can disconnect WhatsApp from your Waiter console and request deletion of your account information by writing to ${MAIL}.` },
        ],
      },
      {
        id: 'questions',
        title: 'Questions?',
        blocks: [
          { p: `${MAIL} · ${PHONE}. See also the [Waiter privacy policy](/waiter/privacy).` },
        ],
      },
    ],
  },
}
