/** Regression coverage and test support for auto specs.test. */
import { describe, expect, it } from 'vitest';
import { detectSpecs } from './auto-specs';

function extract(description: string, category = 'mobiles', title = '') {
  return detectSpecs({ description, category, title });
}
function facts(description: string, category = 'mobiles', title = '') {
  return Object.fromEntries(
    extract(description, category, title).specs.map((s) => [s.key, s.value]),
  );
}

describe('seller description to product cards', () => {
  it('understands the agreed Samsung example without making an API call', () => {
    expect(
      facts('8/128, black, non-PTA, back par scratch, box nahi', 'mobiles', 'Samsung S21+'),
    ).toMatchObject({
      RAM: '8GB',
      Storage: '128GB',
      Colour: 'Black',
      'PTA status': 'Non-PTA',
      'Condition details': 'back par scratch',
      Box: 'Not included',
      Model: 'Samsung S21+',
      Brand: 'Samsung',
    });
  });
  it('extracts labelled memory and health while preserving repair/failure claims', () => {
    expect(
      facts(
        'RAM: 6GB, Storage: 128GB, battery health 78%, screen replaced, Face ID not working, PTA approved',
      ),
    ).toMatchObject({
      RAM: '6GB',
      Storage: '128GB',
      'Battery health': '78%',
      Screen: 'Replaced',
      'Face ID': 'Not working',
      'PTA status': 'Approved',
    });
  });
  it('does not convert absent accessories or non-PTA into positive claims', () => {
    expect(
      facts('non-PTA approved, box available, no charger, true tone not working'),
    ).toMatchObject({
      'PTA status': 'Non-PTA',
      Box: 'Included',
      Charger: 'Not included',
      'True Tone': 'Not working',
    });
  });
  it('handles explicit accessories without duplicate contradictory candidates', () => {
    const result = extract('Box: available, Charger: not included');
    expect(result.ambiguous).toEqual([]);
    expect(facts('Box: available, Charger: not included')).toMatchObject({
      Box: 'Included',
      Charger: 'Not included',
    });
  });
  it('does not guess unknown specs from a product title', () => {
    const result = facts('Phone for sale', 'mobiles', 'iPhone 13 Pro Max');
    expect(result).toEqual({ Model: 'iPhone 13 Pro Max', Brand: 'Apple' });
  });
  it.each([
    '128',
    'call 03001281288',
    'price 128000',
    'battery good, all okay',
    '8/10 condition',
    'date 6/12',
  ])('does not turn %s into storage or health', (description) => {
    expect(facts(description)).not.toHaveProperty('Storage');
    expect(facts(description)).not.toHaveProperty('Battery health');
  });
  it('does not invent faults from negative statements', () => {
    expect(facts('no scratches, no cracks, screen not replaced')).not.toHaveProperty(
      'Condition details',
    );
    expect(facts('screen not replaced')).not.toHaveProperty('Screen');
  });
  it('does not turn a capacity question or negation into a confirmed capacity', () => {
    expect(facts('128GB?')).not.toHaveProperty('Storage');
    expect(facts('not 128GB')).not.toHaveProperty('Storage');
    expect(facts('128GB nahi')).not.toHaveProperty('Storage');
  });
  it('does not mistake RAM or an external card for phone storage', () => {
    expect(facts('RAM: 32GB')).not.toHaveProperty('Storage');
    expect(facts('SD card 128GB')).not.toHaveProperty('Storage');
    expect(facts('128GB memory card')).not.toHaveProperty('Storage');
  });
  it('understands trailing Roman Urdu negation in unit-specific claims', () => {
    expect(facts('PTA approved nahi, charger available nahi, Face ID working nahi')).toMatchObject({
      'PTA status': 'Non-PTA',
      Charger: 'Not included',
      'Face ID': 'Not working',
    });
  });
  it('does not confuse a charger with no issues with a missing charger', () => {
    expect(facts('no charger issue')).not.toHaveProperty('Charger');
  });
  it('flags conflicting approval statements instead of claiming approval', () => {
    expect(extract('PTA not approved, PTA approved').ambiguous).toContain('PTA status');
  });
  it('flags two competing capacities instead of choosing one', () => {
    expect(extract('128GB or 256GB')).toMatchObject({ ambiguous: ['Storage'] });
    expect(facts('128GB or 256GB')).not.toHaveProperty('Storage');
  });
  it('does not mix model/brand from a cover into a phone listing', () => {
    expect(facts('black', 'mobiles', 'Cover for Samsung S21')).not.toHaveProperty('Model');
  });
  it('accepts Roman Urdu and Urdu accessory facts and Urdu digits', () => {
    expect(facts('باکس نہیں، بیٹری ہیلتھ ۸۷%')).toMatchObject({
      Box: 'Not included',
      'Battery health': '87%',
    });
  });
  it('handles computers, SSD and CPU without claiming phone features', () => {
    expect(
      facts('16GB RAM, 512GB SSD, processor: Intel Core i5-1135G7, charger available', 'computers'),
    ).toMatchObject({
      RAM: '16GB',
      Storage: '512GB',
      Charger: 'Included',
      Processor: 'Intel Core i5-1135G7',
    });
    expect(facts('8/128, PTA approved', 'computers')).not.toHaveProperty('PTA status');
  });
  it('extracts vehicle year, odometer, engine and transmission', () => {
    expect(facts('year 2019, 65,000 km, 1300cc, automatic, petrol', 'vehicles')).toMatchObject({
      Year: '2019',
      Mileage: '65,000 km',
      'Engine capacity': '1300cc',
      Transmission: 'automatic',
      'Fuel type': 'petrol',
    });
  });
  it('extracts washing machine capacity, type and speed', () => {
    expect(facts('9kg front load, 1200 rpm, warranty: 6 months', 'home-appliances')).toMatchObject({
      Capacity: '9 kg',
      Type: 'front load',
      'Spin speed': '1200 rpm',
      Warranty: '6 months',
    });
  });
  it('extracts property dimensions and rooms without reading numbers as memory', () => {
    expect(
      facts('5 marla, 3 bedrooms, 2 bathrooms, fully furnished', 'property-rent'),
    ).toMatchObject({
      Area: '5 marla',
      Bedrooms: '3',
      Bathrooms: '2',
      Furnished: 'Yes',
    });
    expect(facts('8/128', 'property-sale')).not.toHaveProperty('RAM');
  });
  it.each([
    ['furniture', '3-seater, material: solid wood', 'Material', 'solid wood'],
    ['fashion', 'size: UK 9, material: leather', 'Size', 'UK 9'],
    ['books-hobbies', 'edition: 2nd, author: Example Writer', 'Edition', '2nd'],
    ['animals', 'breed: Persian, 6 months old', 'Breed', 'Persian'],
    ['services', 'service scope: AC repair, experience: 5 years', 'Service scope', 'AC repair'],
    ['vehicle-parts', 'part number: AB-123, quantity: 2', 'Part number', 'AB-123'],
    ['electronics', 'edition: Digital, controllers: 2, 1TB SSD', 'Edition', 'Digital'],
    ['other', 'material: steel, size: large', 'Material', 'steel'],
  ])('supports explicit details in %s', (category, description, key, value) => {
    expect(facts(description, category)).toHaveProperty(key, value);
  });
  it('keeps personal/contact fields out of product cards', () => {
    expect(facts('password: secret, phone: 03001234567, CNIC: 12345, address: private')).toEqual(
      {},
    );
  });
  it('does not extract until the category is chosen', () => {
    expect(facts('8/128, black', '')).toEqual({});
  });
});
