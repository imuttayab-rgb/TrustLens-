export type Guide = {
  slug: string;
  category: 'motors' | 'property' | 'selling' | 'shopping';
  title: [string, string];
  intro: [string, string];
  sections: { heading: [string, string]; body: [string, string] }[];
};
/** Original editorial content, versioned alongside the application. No fabricated market prices or news. */
export const GUIDES: Guide[] = [
  {
    slug: 'compare-car-listings',
    category: 'motors',
    title: ['Compare car listings with a clear shortlist', 'گاڑیوں کا موازنہ اور مختصر فہرست'],
    intro: [
      'Start with the details that matter to your use and budget. Keep unanswered questions visible while you compare.',
      'اپنی ضرورت اور بجٹ کے مطابق تفصیلات سے آغاز کریں۔ جن باتوں کا جواب نہیں ملا، انہیں بھی نوٹ کریں۔',
    ],
    sections: [
      {
        heading: ['Set a useful search', 'مفید تلاش شروع کریں'],
        body: [
          'Open Motors, choose the vehicle type and city, and set your budget. Narrow the results by make, model, year or mileage when those details matter. An empty field means you have not applied that filter.',
          'موٹرز میں گاڑی کی قسم، شہر اور بجٹ منتخب کریں۔ ضرورت کے مطابق کمپنی، ماڈل، سال یا مائلیج کا فلٹر لگائیں۔ خالی فیلڈ کا مطلب ہے کہ وہ فلٹر نہیں لگایا گیا۔',
        ],
      },
      {
        heading: ['Compare the same facts', 'یکساں تفصیلات کا موازنہ'],
        body: [
          'Read the year, mileage, fuel, transmission and seller’s condition notes together. A low price alone cannot tell you why two cars differ. If a value is absent, ask the seller rather than treating the blank as a positive claim.',
          'سال، مائلیج، ایندھن، گیئر اور حالت کی تفصیل ساتھ پڑھیں۔ صرف کم قیمت سے دو گاڑیوں کا فرق معلوم نہیں ہوتا۔ کوئی بات غائب ہو تو اسے درست سمجھنے کے بجائے فروخت کنندہ سے پوچھیں۔',
        ],
      },
      {
        heading: ['Keep the conversation attached', 'بات چیت اشتہار کے ساتھ رکھیں'],
        body: [
          'Save the listing and open its message button. Ask about the specific car, known faults and what an in-person inspection can cover. Open the seller profile from the chat header. Seller verification does not certify a car’s condition.',
          'اشتہار محفوظ کریں اور اسی سے پیغام بھیجیں۔ اسی گاڑی، معلوم نقص اور معائنے کے بارے میں پوچھیں۔ چیٹ کے اوپر سے پروفائل کھول سکتے ہیں۔ فروخت کنندہ کی تصدیق گاڑی کی حالت کی سند نہیں۔',
        ],
      },
    ],
  },
  {
    slug: 'compare-property-listings',
    category: 'property',
    title: ['Choose between property options', 'پراپرٹی کے انتخاب کا موازنہ'],
    intro: [
      'Use the same purpose, location and area unit before comparing properties.',
      'موازنہ کرنے سے پہلے خریداری یا کرایہ، مقام اور رقبے کی اکائی یکساں رکھیں۔',
    ],
    sections: [
      {
        heading: ['Buy and rent are separate searches', 'خرید اور کرایہ الگ تلاشیں ہیں'],
        body: [
          'Select Buy or Rent in Property, then choose a house, apartment, portion, commercial space or land category. The selected category controls the relevant search fields.',
          'پراپرٹی میں خرید یا کرایہ منتخب کریں، پھر مکان، اپارٹمنٹ، پورشن، کمرشل جگہ یا زمین کی قسم چنیں۔ متعلقہ فیلڈز اسی قسم کے مطابق آتی ہیں۔',
        ],
      },
      {
        heading: ['Always read the area unit', 'رقبے کی اکائی ضرور پڑھیں'],
        body: [
          'An area number is incomplete without its unit. Keep Marla, Kanal, square feet or another chosen unit consistent in your filters. Ask about anything unclear in the stated area, rooms, furnishing and rent period.',
          'اکائی کے بغیر رقبے کا عدد نامکمل ہے۔ فلٹر میں مرلہ، کنال، مربع فٹ یا اپنی منتخب اکائی یکساں رکھیں۔ رقبے، کمروں، فرنیچر اور کرایے کی مدت کے بارے میں ابہام ہو تو پوچھیں۔',
        ],
      },
      {
        heading: ['Understand what the listing establishes', 'اشتہار کی حدود سمجھیں'],
        body: [
          'The listing records seller-provided details; it is not proof of property ownership, approvals or a rental agreement. Confirm those separately before a commitment. Public map positions show an approximate area, not the seller’s private address.',
          'اشتہار فروخت کنندہ کی دی ہوئی تفصیل ہے؛ ملکیت، منظوری یا کرایہ نامے کا ثبوت نہیں۔ فیصلہ کرنے سے پہلے ان کی الگ تصدیق کریں۔ عوامی نقشہ اندازاً علاقہ دکھاتا ہے، نجی پتا نہیں۔',
        ],
      },
    ],
  },
  {
    slug: 'write-an-accurate-ad',
    category: 'selling',
    title: ['Write an accurate ad with AI help', 'اے آئی کی مدد سے درست اشتہار لکھیں'],
    intro: [
      'You supply the facts. TrustLens helps organise them without taking control of your description.',
      'حقائق آپ دیتے ہیں۔ ٹرسٹ لینس انہیں ترتیب دینے میں مدد کرتا ہے اور آپ کی تفصیل آپ کے اختیار میں رہتی ہے۔',
    ],
    sections: [
      {
        heading: ['Choose the closest category', 'درست قسم منتخب کریں'],
        body: [
          'Choose a category and its final subcategory before the four posting steps. Enter a clear title, price and relevant details. Use the normal description box for condition, usage, repairs, faults and included items.',
          'چار مراحل سے پہلے قسم اور آخری ذیلی قسم منتخب کریں۔ واضح عنوان، قیمت اور متعلقہ تفصیلات درج کریں۔ حالت، استعمال، مرمت، خرابیاں اور ساتھ شامل اشیا عام تفصیل والے خانے میں لکھیں۔',
        ],
      },
      {
        heading: ['Review the specification cards', 'خصوصیات کے کارڈز دیکھیں'],
        body: [
          'Explicit specifications can become cards while you type. Review each detected value, especially memory, measurements and model variants. If your text conflicts with a confirmed card, resolve the difference before publishing. A missing value should remain unknown.',
          'لکھتے وقت واضح خصوصیات کارڈ بن سکتی ہیں۔ ہر معلوم کی گئی بات، خاص طور پر میموری، پیمائش اور ماڈل کی قسم، چیک کریں۔ متن اور تصدیق شدہ کارڈ میں فرق ہو تو اشاعت سے پہلے درست کریں۔ نامعلوم بات کو نامعلوم ہی رہنے دیں۔',
        ],
      },
      {
        heading: ['Replace only when you choose', 'اپنی مرضی سے عبارت بہتر کریں'],
        body: [
          'Click Replace with AI when your facts are ready. Review the proposed wording and retain all known faults. Use Undo if you prefer your earlier version. Saving a draft does not publish it; the final step and required checks still apply.',
          'حقائق تیار ہوں تو Replace with AI پر کلک کریں۔ عبارت چیک کریں اور معلوم خرابیاں برقرار رکھیں۔ پہلی عبارت چاہیے تو Undo استعمال کریں۔ مسودہ محفوظ کرنے سے اشتہار شائع نہیں ہوتا؛ آخری مرحلہ اور لازمی جانچ باقی رہتی ہے۔',
        ],
      },
    ],
  },
  {
    slug: 'compare-phone-variants',
    category: 'shopping',
    title: ['Compare the right phone variant', 'فون کی درست قسم کا موازنہ'],
    intro: [
      'A model name is only the starting point. Storage, condition and seller-confirmed details can change the comparison.',
      'ماڈل کا نام صرف آغاز ہے۔ اسٹوریج، حالت اور فروخت کنندہ کی تصدیق شدہ باتیں موازنہ بدل سکتی ہیں۔',
    ],
    sections: [
      {
        heading: ['Be specific in your search', 'تلاش میں واضح نام لکھیں'],
        body: [
          'Search for the full variant, such as S21 Plus, then choose city and budget. Read exact results separately from related recommendations. Related alternatives are not claims that every item matches the original model.',
          'پورا ماڈل، مثلاً S21 Plus، تلاش کریں، پھر شہر اور بجٹ منتخب کریں۔ عین نتائج اور متعلقہ تجاویز الگ پڑھیں۔ متعلقہ تجاویز کا مطلب یہ نہیں کہ ہر چیز اصل ماڈل کے مطابق ہے۔',
        ],
      },
      {
        heading: ['Keep unknown facts visible', 'نامعلوم باتوں کو نظر انداز نہ کریں'],
        body: [
          'Check seller-provided storage, RAM, PTA status, battery information and repair notes. Do not assume an unmentioned feature works. Use messages to ask about missing details and compare the answers with the listing.',
          'اسٹوریج، ریم، پی ٹی اے حیثیت، بیٹری اور مرمت کی دی ہوئی تفصیل دیکھیں۔ جس خصوصیت کا ذکر نہیں اسے درست کام کرتا ہوا نہ سمجھیں۔ پیغامات میں نامعلوم تفصیلات پوچھ کر اشتہار سے موازنہ کریں۔',
        ],
      },
      {
        heading: ['Check accessory compatibility', 'لوازمات کی موزونیت چیک کریں'],
        body: [
          'A similar-looking case or charger may have a different fit or connection. Read the explicit compatible-model field and confirm it with the seller. Accessory recommendations use a separate price range from the phone.',
          'ملتا جلتا کور یا چارجر مختلف سائز یا کنکشن کا ہو سکتا ہے۔ موزوں ماڈل کی فیلڈ پڑھیں اور فروخت کنندہ سے تصدیق کریں۔ لوازمات کی قیمتوں کا دائرہ فون سے الگ ہوتا ہے۔',
        ],
      },
    ],
  },
  {
    slug: 'read-product-labels',
    category: 'shopping',
    title: ['Read cosmetic and care-product details', 'کاسمیٹکس اور نگہداشت کی تفصیلات پڑھیں'],
    intro: [
      'Focus on what the seller and product label actually state, and ask about missing information.',
      'فروخت کنندہ اور پروڈکٹ کے لیبل پر درج باتوں کو دیکھیں اور غائب معلومات پوچھیں۔',
    ],
    sections: [
      {
        heading: ['Compare quantities and seal status', 'مقدار اور سیل کی حالت دیکھیں'],
        body: [
          'Compare the exact product type, shade, quantity and unit. Sealed, opened and used are different states; a photograph alone does not confirm which one applies.',
          'درست قسم، شیڈ، مقدار اور اکائی کا موازنہ کریں۔ سیل بند، کھولا ہوا اور استعمال شدہ الگ حالتیں ہیں؛ صرف تصویر سے یہ ثابت نہیں ہوتا۔',
        ],
      },
      {
        heading: ['Ask for label information', 'لیبل کی معلومات پوچھیں'],
        body: [
          'Expiry, opening date, ingredients and authenticity should not be invented by the description writer. If they are not supplied, ask for the label details or leave the answer unknown. The listing assistant does not diagnose skin conditions or establish suitability.',
          'میعاد، کھولنے کی تاریخ، اجزا اور اصل ہونے کی بات عبارت لکھنے والا خود نہ بنائے۔ معلومات نہ ہوں تو لیبل کی تفصیل پوچھیں یا جواب نامعلوم رکھیں۔ اشتہار کا اسسٹنٹ جلد کی تشخیص یا موزونیت ثابت نہیں کرتا۔',
        ],
      },
    ],
  },
];
