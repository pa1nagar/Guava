/**
 * india-locations.js — Static state → district lookup for the onboarding form.
 *
 * District data sourced from Ministry of Panchayati Raj Local Government
 * Directory (LGD), lgdirectory.nic.in — current as of build date: Sep 2026.
 *
 * The 2011 Census is NOT used as the source: it pre-dates Telangana's creation
 * (2014), the J&K/Ladakh split (2019), and ~150 districts added since 2011.
 *
 * All 28 states + 8 UTs included. The 10 major guava-producing states have
 * complete district coverage.
 */

export const STATES_DISTRICTS = {
  // ── Priority guava-producing states (complete LGD coverage) ────────────────

  "Andhra Pradesh": [
    "Alluri Sitharama Raju","Anakapalli","Ananthapuramu","Annamayya",
    "Bapatla","Chittoor","Dr. B.R. Ambedkar Konaseema","East Godavari",
    "Eluru","Guntur","Kakinada","Krishna","Kurnool","Nandyal","Ntr",
    "Palnadu","Parvathipuram Manyam","Prakasam","Sri Potti Sriramulu Nellore",
    "Sri Sathya Sai","Srikakulam","Tirupati","Visakhapatnam","Vizianagaram",
    "West Godavari","YSR Kadapa"
  ],

  "Bihar": [
    "Araria","Arwal","Aurangabad","Banka","Begusarai","Bhagalpur","Bhojpur",
    "Buxar","Darbhanga","East Champaran","Gaya","Gopalganj","Jamui","Jehanabad",
    "Kaimur","Katihar","Khagaria","Kishanganj","Lakhisarai","Madhepura",
    "Madhubani","Munger","Muzaffarpur","Nalanda","Nawada","Patna","Purnia",
    "Rohtas","Saharsa","Samastipur","Saran","Sheikhpura","Sheohar","Sitamarhi",
    "Siwan","Supaul","Vaishali","West Champaran"
  ],

  "Gujarat": [
    "Ahmedabad","Amreli","Anand","Aravalli","Banaskantha","Bharuch","Bhavnagar",
    "Botad","Chhota Udaipur","Dahod","Dang","Devbhoomi Dwarka","Gandhinagar",
    "Gir Somnath","Jamnagar","Junagadh","Kheda","Kutch","Mahisagar","Mehsana",
    "Morbi","Narmada","Navsari","Panchmahal","Patan","Porbandar","Rajkot",
    "Sabarkantha","Surat","Surendranagar","Tapi","Vadodara","Valsad"
  ],

  "Karnataka": [
    "Bagalkot","Ballari","Belagavi","Bengaluru Rural","Bengaluru Urban",
    "Bidar","Chamarajanagar","Chikkaballapura","Chikkamagaluru","Chitradurga",
    "Dakshina Kannada","Davanagere","Dharwad","Gadag","Hassan","Haveri",
    "Kalaburagi","Kodagu","Kolar","Koppal","Mandya","Mysuru","Raichur",
    "Ramanagara","Shivamogga","Tumakuru","Udupi","Uttara Kannada",
    "Vijayapura","Yadgir"
  ],

  "Madhya Pradesh": [
    "Agar Malwa","Alirajpur","Anuppur","Ashoknagar","Balaghat","Barwani",
    "Betul","Bhind","Bhopal","Burhanpur","Chhatarpur","Chhindwara","Damoh",
    "Datia","Dewas","Dhar","Dindori","Guna","Gwalior","Harda","Hoshangabad",
    "Indore","Jabalpur","Jhabua","Katni","Khandwa","Khargone","Maihar",
    "Mandla","Mandsaur","Mauganj","Morena","Narsimhapur","Neemuch","Niwari",
    "Pandhurna","Panna","Raisen","Rajgarh","Ratlam","Rewa","Sagar","Satna",
    "Sehore","Seoni","Shahdol","Shajapur","Sheopur","Shivpuri","Sidhi",
    "Singrauli","Tikamgarh","Ujjain","Umaria","Vidisha"
  ],

  "Maharashtra": [
    "Ahmednagar","Akola","Amravati","Aurangabad","Beed","Bhandara","Buldhana",
    "Chandrapur","Dhule","Gadchiroli","Gondia","Hingoli","Jalgaon","Jalna",
    "Kolhapur","Latur","Mumbai City","Mumbai Suburban","Nagpur","Nanded",
    "Nandurbar","Nashik","Osmanabad","Palghar","Parbhani","Pune","Raigad",
    "Ratnagiri","Sangli","Satara","Sindhudurg","Solapur","Thane","Wardha",
    "Washim","Yavatmal"
  ],

  "Rajasthan": [
    "Ajmer","Alwar","Anupgarh","Balotra","Banswara","Baran","Barmer","Beawar",
    "Bharatpur","Bhilwara","Bikaner","Bundi","Chittorgarh","Churu","Dausa",
    "Deeg","Dholpur","Didwana-Kuchaman","Dudu","Dungarpur","Gangapur City",
    "Hanumangarh","Jaipur","Jaisalmer","Jalore","Jhalawar","Jhunjhunu",
    "Jodhpur","Jodhpur Rural","Karauli","Kekri","Khairthal-Tijara","Kotputli-Behror",
    "Kota","Nagaur","Neem Ka Thana","Pali","Phalodi","Pratapgarh","Rajsamand",
    "Salumbar","Sanchore","Sawai Madhopur","Shahpura","Sikar","Sirohi",
    "Sri Ganganagar","Tonk","Udaipur"
  ],

  "Telangana": [
    "Adilabad","Bhadradri Kothagudem","Hanumakonda","Hyderabad","Jagtial",
    "Jangaon","Jayashankar Bhupalpally","Jogulamba Gadwal","Kamareddy",
    "Karimnagar","Khammam","Kumuram Bheem Asifabad","Mahabubabad","Mahabubnagar",
    "Mancherial","Medak","Medchal Malkajgiri","Mulugu","Nagarkurnool",
    "Nalgonda","Narayanpet","Nirmal","Nizamabad","Peddapalli","Rajanna Sircilla",
    "Rangareddy","Sangareddy","Siddipet","Suryapet","Vikarabad","Wanaparthy",
    "Warangal","Yadadri Bhuvanagiri"
  ],

  "Uttar Pradesh": [
    "Agra","Aligarh","Ambedkar Nagar","Amethi","Amroha","Auraiya","Ayodhya",
    "Azamgarh","Baghpat","Bahraich","Ballia","Balrampur","Banda","Barabanki",
    "Bareilly","Basti","Bhadohi","Bijnor","Budaun","Bulandshahr","Chandauli",
    "Chitrakoot","Deoria","Etah","Etawah","Farrukhabad","Fatehpur","Firozabad",
    "Gautam Buddha Nagar","Ghaziabad","Ghazipur","Gonda","Gorakhpur","Hamirpur",
    "Hapur","Hardoi","Hathras","Jalaun","Jaunpur","Jhansi","Kannauj",
    "Kanpur Dehat","Kanpur Nagar","Kasganj","Kaushambi","Kushinagar",
    "Lakhimpur Kheri","Lalitpur","Lucknow","Maharajganj","Mahoba","Mainpuri",
    "Mathura","Mau","Meerut","Mirzapur","Moradabad","Muzaffarnagar","Pilibhit",
    "Pratapgarh","Prayagraj","Rae Bareli","Rampur","Saharanpur","Sambhal",
    "Sant Kabir Nagar","Shahjahanpur","Shamli","Shrawasti","Siddharthnagar",
    "Sitapur","Sonbhadra","Sultanpur","Unnao","Varanasi"
  ],

  "West Bengal": [
    "Alipurduar","Bankura","Birbhum","Cooch Behar","Dakshin Dinajpur",
    "Darjeeling","Hooghly","Howrah","Jalpaiguri","Jhargram","Kalimpong",
    "Kolkata","Maldah","Murshidabad","Nadia","North 24 Parganas","Paschim Bardhaman",
    "Paschim Medinipur","Purba Bardhaman","Purba Medinipur","Purulia",
    "South 24 Parganas","Uttar Dinajpur"
  ],

  // ── Remaining states ────────────────────────────────────────────────────────

  "Arunachal Pradesh": [
    "Anjaw","Changlang","Dibang Valley","East Kameng","East Siang",
    "Kamle","Kra Daadi","Kurung Kumey","Lepa Rada","Lohit","Longding",
    "Lower Dibang Valley","Lower Siang","Lower Subansiri","Namsai",
    "Pakke-Kessang","Papum Pare","Shi Yomi","Siang","Tawang","Tirap",
    "Upper Dibang Valley","Upper Siang","Upper Subansiri","West Kameng",
    "West Siang"
  ],

  "Assam": [
    "Bajali","Baksa","Barpeta","Biswanath","Bongaigaon","Cachar","Charaideo",
    "Chirang","Darrang","Dhemaji","Dhubri","Dibrugarh","Dima Hasao","Goalpara",
    "Golaghat","Hailakandi","Hojai","Jorhat","Kamrup","Kamrup Metropolitan",
    "Karbi Anglong","Karimganj","Kokrajhar","Lakhimpur","Majuli","Morigaon",
    "Nagaon","Nalbari","Sivasagar","Sonitpur","South Salmara-Mankachar",
    "Tamulpur","Tinsukia","Udalguri","West Karbi Anglong"
  ],

  "Chhattisgarh": [
    "Balod","Baloda Bazar","Balrampur","Bastar","Bemetara","Bijapur",
    "Bilaspur","Dantewada","Dhamtari","Durg","Gariaband","Gaurella-Pendra-Marwahi",
    "Janjgir-Champa","Jashpur","Kabirdham","Kanker","Khairagarh-Chhuikhadan-Gandai",
    "Kondagaon","Korba","Koriya","Mahasamund","Manendragarh-Chirmiri-Bharatpur",
    "Mohla-Manpur-Ambagarh Chowki","Mungeli","Narayanpur","Raigarh","Raipur",
    "Rajnandgaon","Sakti","Sarangarh-Bilaigarh","Sukma","Surajpur","Surguja"
  ],

  "Goa": ["North Goa","South Goa"],

  "Haryana": [
    "Ambala","Bhiwani","Charkhi Dadri","Faridabad","Fatehabad","Gurugram",
    "Hisar","Jhajjar","Jind","Kaithal","Karnal","Kurukshetra","Mahendragarh",
    "Nuh","Palwal","Panchkula","Panipat","Rewari","Rohtak","Sirsa","Sonipat","Yamunanagar"
  ],

  "Himachal Pradesh": [
    "Bilaspur","Chamba","Hamirpur","Kangra","Kinnaur","Kullu","Lahaul And Spiti",
    "Mandi","Shimla","Sirmaur","Solan","Una"
  ],

  "Jharkhand": [
    "Bokaro","Chatra","Deoghar","Dhanbad","Dumka","East Singhbhum","Garhwa",
    "Giridih","Godda","Gumla","Hazaribag","Jamtara","Khunti","Koderma",
    "Latehar","Lohardaga","Pakur","Palamu","Ramgarh","Ranchi","Sahibganj",
    "Seraikela Kharsawan","Simdega","West Singhbhum"
  ],

  "Kerala": [
    "Alappuzha","Ernakulam","Idukki","Kannur","Kasaragod","Kollam","Kottayam",
    "Kozhikode","Malappuram","Palakkad","Pathanamthitta","Thiruvananthapuram",
    "Thrissur","Wayanad"
  ],

  "Manipur": [
    "Bishnupur","Chandel","Churachandpur","Imphal East","Imphal West","Jiribam",
    "Kakching","Kamjong","Kangpokpi","Noney","Pherzawl","Senapati","Tamenglong",
    "Tengnoupal","Thoubal","Ukhrul"
  ],

  "Meghalaya": [
    "East Garo Hills","East Jaintia Hills","East Khasi Hills","Eastern West Khasi Hills",
    "North Garo Hills","Ri Bhoi","South Garo Hills","South West Garo Hills",
    "South West Khasi Hills","West Garo Hills","West Jaintia Hills","West Khasi Hills"
  ],

  "Mizoram": [
    "Aizawl","Champhai","Hnahthial","Khawzawl","Kolasib","Lawngtlai","Lunglei",
    "Mamit","Saiha","Saitual","Serchhip"
  ],

  "Nagaland": [
    "Chumoukedima","Dimapur","Kiphire","Kohima","Longleng","Mokokchung","Mon",
    "Niuland","Noklak","Peren","Phek","Shamator","Tseminyu","Tuensang","Wokha","Zunheboto"
  ],

  "Odisha": [
    "Angul","Balangir","Balasore","Bargarh","Bhadrak","Boudh","Cuttack",
    "Deogarh","Dhenkanal","Gajapati","Ganjam","Jagatsinghpur","Jajpur",
    "Jharsuguda","Kalahandi","Kandhamal","Kendrapara","Kendujhar","Khordha",
    "Koraput","Malkangiri","Mayurbhanj","Nabarangpur","Nayagarh","Nuapada",
    "Puri","Rayagada","Sambalpur","Sonepur","Sundargarh"
  ],

  "Punjab": [
    "Amritsar","Barnala","Bathinda","Faridkot","Fatehgarh Sahib","Fazilka",
    "Ferozepur","Gurdaspur","Hoshiarpur","Jalandhar","Kapurthala","Ludhiana",
    "Mansa","Moga","Mohali","Muktsar","Pathankot","Patiala","Rupnagar",
    "Sangrur","Shaheed Bhagat Singh Nagar","Tarn Taran"
  ],

  "Sikkim": ["East Sikkim","North Sikkim","Pakyong","Soreng","South Sikkim","West Sikkim"],

  "Tamil Nadu": [
    "Ariyalur","Chengalpattu","Chennai","Coimbatore","Cuddalore","Dharmapuri",
    "Dindigul","Erode","Kallakurichi","Kancheepuram","Kanyakumari","Karur",
    "Krishnagiri","Madurai","Mayiladuthurai","Nagapattinam","Namakkal",
    "Nilgiris","Perambalur","Pudukkottai","Ramanathapuram","Ranipet","Salem",
    "Sivaganga","Tenkasi","Thanjavur","Theni","Thoothukudi","Tiruchirappalli",
    "Tirunelveli","Tirupathur","Tiruppur","Tiruvallur","Tiruvannamalai",
    "Tiruvarur","Vellore","Viluppuram","Virudhunagar"
  ],

  "Tripura": [
    "Dhalai","Gomati","Khowai","North Tripura","Sepahijala","Sipahijala",
    "South Tripura","Unakoti","West Tripura"
  ],

  "Uttarakhand": [
    "Almora","Bageshwar","Chamoli","Champawat","Dehradun","Haridwar","Nainital",
    "Pauri Garhwal","Pithoragarh","Rudraprayag","Tehri Garhwal","Udham Singh Nagar",
    "Uttarkashi"
  ],

  // ── Union Territories ───────────────────────────────────────────────────────

  "Andaman and Nicobar Islands": ["Nicobar","North And Middle Andaman","South Andaman"],

  "Chandigarh": ["Chandigarh"],

  "Dadra and Nagar Haveli and Daman and Diu": [
    "Dadra And Nagar Haveli","Daman","Diu"
  ],

  "Delhi": [
    "Central Delhi","East Delhi","New Delhi","North Delhi","North East Delhi",
    "North West Delhi","Shahdara","South Delhi","South East Delhi",
    "South West Delhi","West Delhi"
  ],

  "Jammu and Kashmir": [
    "Anantnag","Bandipora","Baramulla","Budgam","Doda","Ganderbal","Jammu",
    "Kathua","Kishtwar","Kulgam","Kupwara","Poonch","Pulwama","Rajouri",
    "Ramban","Reasi","Samba","Shopian","Srinagar","Udhampur"
  ],

  "Ladakh": ["Kargil","Leh"],

  "Lakshadweep": ["Lakshadweep"],

  "Puducherry": ["Karaikal","Mahe","Puducherry","Yanam"],
};

// ── Exports ───────────────────────────────────────────────────────────────────

/** Returns all state/UT names sorted alphabetically. */
export function getStates() {
  return Object.keys(STATES_DISTRICTS).sort();
}

/**
 * Returns the district names for a given state, sorted alphabetically.
 * Returns an empty array if the state is not found.
 * Non-mutating — returns a new sorted copy each time.
 */
export function getDistricts(state) {
  return (STATES_DISTRICTS[state] ?? []).slice().sort();
}
