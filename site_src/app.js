/* Private leasing comparison page. Data comes from data.js (window.PAGE_DATA). */
(function () {
  const DATA = window.PAGE_DATA;
  if (!DATA) { document.body.textContent = "Missing data.js"; return; }

  const PT = { "Petrol": "Petrol", "Petrol MHEV": "MHEV", "Hybrid": "HEV", "PHEV": "PHEV", "EREV": "EREV", "EV": "EV", "Diesel": "Diesel" };
  const SLOT = { "Shlomo Sixt|Direct": "sd", "Shlomo Sixt|HTZone": "sh", "Pery|Direct": "pd", "Albar|HTZone": "ah" };
  const SLOT_NAME = { sd: "Shlomo direct", sh: "Shlomo via HTZone", pd: "Pery direct", ah: "Albar via HTZone" };
  const CHIP_IDS = [["comp","Comprehensive","מקיף"],["maint","Maintenance","טיפולים"],["lic","Licensing","אגרה"],["tyres","Tyres","צמיגים"],["repl","Replacement car","רכב חלופי"]];
  const CNAME = {
    adv:["Advance","מקדמה"], mo:["Monthly lease payment","תשלום חודשי"], disc:["Online discount","הנחת אונליין"],
    cpi:["CPI linkage","הצמדה למדד"], energy:["Fuel / electricity","דלק / חשמל"],
    comp:["Comprehensive insurance (מקיף)","ביטוח מקיף"], compul:["Compulsory insurance (חובה)","ביטוח חובה"],
    third:["Third-party liability","צד ג'"], ded:["Deductible / waiver","השתתפות עצמית / ביטול"],
    lic:["Licensing fee (אגרת רישוי)","אגרת רישוי"], maint:["Maintenance","טיפולים"], tyres:["Tyres","צמיגים"],
    brakes:["Brakes","בלמים"], battery:["Battery","מצבר"], repl:["Replacement car","רכב חלופי"],
    tow:["Towing / roadside","גרירה / חילוץ"], wash:["Car wash","שטיפה"], driver:["Young / new driver","נהג צעיר / חדש"],
    xkm:["Excess km","ק\"מ עודף"], buy:["Buyout at end","רכישה בסוף"]
  };
  const INCLUDED_KM = DATA.defaults.included_km || 20000;
  const LIC = DATA.licensing;

  const state = {
    lang: (function(){ try { return localStorage.getItem("leaseLang")==="en" ? "en" : "he"; } catch(e){ return "he"; } })(),
    km: String(DATA.defaults.km),
    petrol: String(DATA.defaults.petrol ?? ""),
    diesel: DATA.defaults.diesel == null ? "" : String(DATA.defaults.diesel),
    elec: String(DATA.defaults.elec ?? ""),
    infl: String(DATA.defaults.infl ?? "2.0"),
    xRate: DATA.defaults.xRate == null ? "" : String(DATA.defaults.xRate),
    shDisc: !!DATA.defaults.shDisc,
    peryMaint: !!DATA.defaults.peryMaint,
    cmp: !!DATA.defaults.cmp,
    co: "all", ch: "all", fuel: "all", q: "",
    sortKey: "effNom", dir: "asc", view: "offer",
    sel: (DATA.offers.find(o => o.key==="P-27") || DATA.offers[0] || {}).key
  };

  const $ = (id) => document.getElementById(id);
  const HE = () => state.lang === "he";
  const L = (en, he) => HE() ? he : en;
  const tr = (s) => (HE() && DATA.i18n && DATA.i18n[s] != null) ? DATA.i18n[s] : s;
  const ISO = (s) => HE() ? ("\u2066" + s + "\u2069") : s;
  const nis = (n) => "₪" + Math.round(n).toLocaleString("en-US");
  const ns = () => L("not stated", "לא צוין");
  const num = (s) => { const v = parseFloat(s); return isFinite(v) ? v : null; };
  const signed = (n) => (n > 0 ? "+" : "") + nis(n);

  function heOf(map, s){ return (HE() && map && map[s]) ? map[s] : s; }
  function cn(o){
    const c = o.canon, pt = PT[o.fuel] || o.fuel;
    return c ? { make:c.make, model:c.model, trim:c.trim, variant:c.variant||"", pt } :
      { make:o.make, model:o.model, trim:"", variant:"", pt };
  }
  function nameOf(o){
    const c = cn(o);
    if (!HE()) return [c.make, c.model, c.trim].filter(Boolean).join(" ");
    return [heOf(DATA.canonical.make_he, c.make), heOf(DATA.canonical.model_he, c.model), heOf(DATA.canonical.trim_he, c.trim)].filter(Boolean).join(" ");
  }
  function varName(v){ return heOf(DATA.canonical.variant_he, v); }
  function slotOf(o){ return SLOT[o.co + "|" + o.ch] || "sd"; }
  function grpKey(o){ const c=cn(o); return [c.make,c.model,c.trim,c.pt].join("|"); }

  function licGroup(o){
    const rg = LIC.registry_group || {};
    if (o.reg && rg[o.reg]) return rg[o.reg];
    if (o.list == null) return null;
    return 1 + (LIC.bands||[]).filter(b => o.list > b).length;
  }
  function licOfficial(o, inp){
    if (o.co === "Albar") return false;
    if (o.co === "Pery" && inp.cmp && o.ad && o.ad[4] != null) return false;
    return true;
  }
  function isCpi(o){
    if (o.co === "Shlomo Sixt") return true;
    if (o.co === "Albar") return o.key !== "H-166284";
    return false;
  }

  function inputs(){
    return {
      km: num(state.km) || 0,
      petrol: num(state.petrol),
      diesel: num(state.diesel),
      elec: num(state.elec),
      infl: num(state.infl) || 0,
      xRate: num(state.xRate),
      shDisc: state.shDisc, peryMaint: state.peryMaint, cmp: state.cmp
    };
  }

  function calc(o, inp){
    const flags = [];
    let pkgKm = INCLUDED_KM, moAtKm = o.mo;
    if (o.co === "Pery" && o.ko && o.ko.length){
      const opts = o.ko.map(p => ({km:p[0]*1000, mo:p[1]})).sort((a,b)=>a.km-b.km);
      const fit = opts.find(p => p.km >= inp.km) || opts[opts.length-1];
      pkgKm = fit.km; moAtKm = fit.mo;
    }
    if (o.key === "H-166284") flags.push("included km not stated (20,000/yr assumed)");
    const excessKm = Math.max(0, inp.km - pkgKm);
    let excessYr = 0;
    if (excessKm > 0){
      if (inp.xRate != null && inp.xRate > 0) excessYr = excessKm * inp.xRate;
      else { excessYr = null; flags.push("excess km not priced"); }
    }
    const fuelPrice = o.fuel === "Diesel" ? inp.diesel : inp.petrol;
    let perKm = null;
    if (o.kwh != null){
      if (inp.elec != null) perKm = (o.kwh/100)*inp.elec;
      else flags.push("no electricity price");
    } else if (o.l100 != null && fuelPrice != null) perKm = (o.l100/100)*fuelPrice;
    else flags.push(o.l100 == null ? "no official consumption" : "no fuel price");
    if (o.fuel === "PHEV" || o.fuel === "EREV") flags.push("charging electricity not included");
    const energyYr = perKm != null ? perKm * inp.km : null;
    const lgrp = licGroup(o);
    const licYr = licOfficial(o,inp) && lgrp != null ? LIC.fee_up_to_3_years[lgrp-1] + LIC.broadcasting_levy : null;
    if (licOfficial(o,inp) && lgrp == null) flags.push("licensing fee not stated (no list price)");
    const licN = Math.ceil((o.term||36)/12);
    let extraMo = 0;
    if (o.co === "Pery" && o.ad){
      if ((inp.peryMaint || inp.cmp) && o.ad[3] != null) extraMo += o.ad[3];
      if (inp.cmp && o.ad[4] != null) extraMo += o.ad[4];
    }
    const empty = {pkgKm, moAtKm, excessKm, excessYr, perKm, energyYr, lease:null, totalNom:null, totalInf:null, effNom:null, effInf:null, flags, licYr, licN};
    if (moAtKm == null || o.adv == null) return empty;
    const disc = (o.co==="Shlomo Sixt" && o.ch==="Direct" && inp.shDisc) ? 3000 : 0;
    const monthly = moAtKm + extraMo;
    const lease = o.adv + monthly * o.term - disc;
    const years = o.term / 12;
    const cpiLinked = isCpi(o);
    let totalNom = lease, totalInf = o.adv - disc;
    for (let y=0; y<years; y++){
      const f = Math.pow(1+inp.infl/100, y);
      totalNom += (energyYr||0) + (excessYr||0) + (licYr||0);
      totalInf += 12*moAtKm*(cpiLinked?f:1) + 12*extraMo + (energyYr||0)*f + (excessYr||0) + (licYr||0)*f;
    }
    return {pkgKm, moAtKm, excessKm, excessYr, perKm, energyYr, lease, totalNom, totalInf, effNom: totalNom/o.term, effInf: totalInf/o.term, flags, licYr, licN};
  }

  function stLab(id, s){
    if (id==="lic" && s==="sep") return L("✗ Not included – computed from official schedule", "✗ לא כלול – מחושב לפי התעריף הרשמי");
    if (s==="inc") return L("✓ Included","✓ כלול");
    if (s==="opt") return L("+ Optional add-on","+ תוספת אופציונלית");
    if (s==="sep") return L("✗ Not included – paid separately","✗ לא כלול – משולם בנפרד");
    return L("? Not stated","? לא צוין");
  }
  const stMark = (s) => s==="inc"?"✓":s==="opt"?"+":s==="sep"?"✗":"?";

  function comps(o, c, inp){
    const S = o.co==="Shlomo Sixt", P = o.co==="Pery", Hz = o.ch==="HTZone", T=o.term;
    const ad = (i) => (o.ad && o.ad[i] != null) ? o.ad[i] : null;
    const dp=L("Deal page","עמוד העסקה"), op=L("Pery order page (API)","עמוד ההזמנה של פרי (API)");
    const hz=L("HTZone item page","עמוד הפריט ב-HTZone"), club=L("Shlomo club terms","תנאי המועדון של שלמה");
    const pdf=L("Shlomo promo PDF","PDF המבצע של שלמה"), cmpd=L("Computed (your inputs)","מחושב (לפי הנתונים שלך)");
    const r = (id,st,note,pm,inT,src,tot) => ({id,st,note,pm,tot: tot!==undefined?tot:(pm!=null?pm*T:null),inT,src});
    const sSrc = Hz?hz:dp, rows=[];
    rows.push(r("adv","inc", o.adv==null?ns():(o.advReg!=null?L("club advance (regular "+nis(o.advReg)+")","מקדמת מועדון (רגילה "+nis(o.advReg)+")"):""), null, o.adv!=null?"y":"n", sSrc, o.adv));
    rows.push(r("mo","inc",(o.co==="Albar"?L("'from' price; ","מחיר \"החל מ\"; "):"")+(P&&o.ko&&o.ko.length?L("at the "+c.pkgKm/1000+"k km/yr package","לפי חבילת "+c.pkgKm/1000+" אלף ק\"מ בשנה"):L(INCLUDED_KM.toLocaleString("en-US")+" km/yr included",INCLUDED_KM.toLocaleString("en-US")+" ק\"מ בשנה כלולים")), c.moAtKm, c.moAtKm!=null?"y":"n", P&&o.ko&&o.ko.length?op:sSrc));
    if (S && !Hz && inp.shDisc) rows.push(r("disc","inc",L("₪3,000 off total payments (deals signed by 30.11.2026)","₪3,000 הנחה מסך התשלומים (לעסקאות עד 30.11.2026)"),null,"y",pdf,-3000));
    let cpiAmt=0;
    if (c.moAtKm!=null) for (let y=0;y<(T/12);y++) cpiAmt += 12*c.moAtKm*(Math.pow(1+inp.infl/100,y)-1);
    if (isCpi(o)) rows.push(r("cpi","inc",L("Payments are CPI-linked; estimated at "+inp.infl+"%/yr","התשלומים צמודי מדד; הערכה לפי "+inp.infl+"% בשנה"), c.moAtKm!=null?cpiAmt/T:null,"i",(S?(Hz?L("Shlomo terms (not repeated on HTZone)","תנאי שלמה (לא מצוין שוב ב-HTZone)"):dp):L("HTZone fine print","אותיות קטנות ב-HTZone"))+" · "+cmpd));
    else rows.push(r("cpi","ns",L("CPI linkage not stated – treated as fixed","הצמדה למדד לא צוינה – נחשב קבוע"),null,"n",P?L("Gap: not published","פער: לא פורסם"):hz));
    if (c.energyYr!=null) rows.push(r("energy","sep",L("Your cost; WLTP consumption × your price","על חשבונך; צריכת WLTP × המחיר שהזנת")+(o.fuel==="PHEV"||o.fuel==="EREV"?L(" (charging electricity not included)"," (חשמל לטעינה לא כלול)"):""), c.energyYr/12,"y",cmpd,c.energyYr*(T/12)));
    else rows.push(r("energy","sep",L("Your cost; not computable (","על חשבונך; לא ניתן לחשב (")+c.flags.map(tr).join(", ")+")",null,"n",cmpd));
    if (P) rows.push(r("comp","inc",L("Insurance package","חבילת ביטוח"),null,"y",op));
    else if (S) rows.push(r("comp","inc",L("Damage cover via self-insurance","כיסוי נזקים בביטוח עצמי"),null,"y",sSrc));
    else rows.push(r("comp","inc",L("Limited self-cover (drivers 24+, not new, clean record)","כיסוי עצמי מוגבל (נהגים מעל 24, לא חדשים, ללא עבר)"),null,"y",hz));
    rows.push(r("compul","inc","",null,"y",P?op:sSrc));
    rows.push(r("third","ns",L("Not mentioned","לא מוזכר"),null,"n",P?op:sSrc));
    if (S) rows.push(r("ded","opt",L("Deductible amounts not stated; deductible + return-to-value waiver","גובה ההשתתפות העצמית לא צוין; ביטול השתתפות עצמית + השבה לקדמות")+(Hz?L(" (club; regular ₪145)"," (מועדון; רגיל ₪145)"):""), Hz?99:145,"n",Hz?hz:club));
    else if (P) rows.push(r("ded","opt",L("Deductible amounts not stated","גובה ההשתתפות לא צוין"), ad(1)!=null&&ad(2)!=null?ad(1)+ad(2):null,"n",op));
    else rows.push(r("ded","ns",L("Deductible amounts and waiver not stated","גובה ההשתתפות העצמית וביטולה לא צוינו"),null,"n",hz));
    const lg2 = licGroup(o);
    const licSrc = L("MoT fee order, Apr 2026","צו האגרות של משרד התחבורה, אפריל 2026");
    if (o.co!=="Albar" && !(P && inp.cmp && ad(4)!=null)){
      const pre = S ? (Hz?L("Not mentioned on HTZone; Shlomo terms: paid yearly by you. ","לא מוזכרת ב-HTZone; בתנאי שלמה: משולמת שנתית על ידך. "):L("Paid yearly by you; Shlomo does not state the amount. ","משולמת שנתית על ידך; שלמה לא מציינת את הסכום. "))
        : L("Not in the lease unless you pick Pery's add-on ("+(ad(4)!=null?"₪"+ad(4)+"/mo":"price not stated")+"). ","לא כלולה בליסינג אלא אם תבחר בתוספת של פרי ("+(ad(4)!=null?"₪"+ad(4)+" לחודש":"מחיר לא צוין")+"). ");
      if (c.licYr!=null && lg2!=null){
        const fromReg = !!(o.reg && LIC.registry_group && LIC.registry_group[o.reg]);
        rows.push(r("lic","sep", pre+L("Official 2026 fee: price group "+lg2+(fromReg?" (registry)":" (from list price)")+", "+nis(c.licYr-LIC.broadcasting_levy)+" + "+nis(LIC.broadcasting_levy)+" broadcasting levy = "+nis(c.licYr)+"/yr × "+c.licN+" renewals; CPI-updated every April (inflation-adjusted total)","אגרה רשמית 2026: קבוצת מחיר "+lg2+(fromReg?" (מאגר הרכב)":" (לפי מחיר המחירון)")+", "+nis(c.licYr-LIC.broadcasting_levy)+" + "+nis(LIC.broadcasting_levy)+" לתאגיד השידור = "+nis(c.licYr)+" לשנה × "+c.licN+" חידושים; מתעדכנת לפי המדד בכל אפריל (בסך המותאם לאינפלציה)"), c.licYr/12,"y",licSrc,c.licYr*c.licN));
      } else rows.push(r("lic","ns", pre+L("List price not stated – price group can't be assigned","מחיר המחירון לא צוין – אי אפשר לקבוע קבוצת מחיר"),null,"n",sSrc));
    } else if (P) rows.push(r("lic","opt",L("Pery's add-on, paid via the lease (used instead of the official fee)","התוספת של פרי, משולמת דרך הליסינג (במקום האגרה הרשמית)"),ad(4),"y",op));
    else rows.push(r("lic","inc",L("Included for the whole term","כלולה לכל התקופה"),null,"y",hz));
    if (S) rows.push(r("maint","inc",L("Servicing per manufacturer incl. brake pads","טיפולים לפי היצרן כולל בלמים"),null,"y",sSrc));
    else if (P) rows.push(r("maint","opt",L("Periodic maintenance package","חבילת טיפולים תקופתיים"),ad(3),(inp.peryMaint||inp.cmp)&&ad(3)!=null?"y":"n",op));
    else rows.push(r("maint","inc",L("Periodic servicing per manufacturer","טיפולים תקופתיים לפי היצרן"),null,"y",hz));
    if (S) rows.push(r("tyres","opt",L("Extended pack","חבילה מורחבת")+(Hz?L(" ₪15/mo club (regular ₪39)"," ₪15 לחודש במועדון (רגיל ₪39)"):L(" ₪39/mo"," ₪39 לחודש")), Hz?15:39,"n",Hz?hz:club));
    else if (P) rows.push(r("tyres","opt","",ad(6),"n",op));
    else rows.push(r("tyres","ns",L("Not mentioned","לא מוזכר"),null,"n",hz));
    if (P) rows.push(r("brakes","opt","",ad(5),"n",op));
    else if (S) rows.push(r("brakes","inc",L("Included with servicing","כלול בטיפולים"),null,"y",sSrc));
    else rows.push(r("brakes","ns","","","n",hz));
    if (P) rows.push(r("battery","opt","",ad(8),"n",op));
    else rows.push(r("battery","opt",S?L("In the extended pack","בחבילה המורחבת"):L("Not mentioned","לא מוזכר"), S?(Hz?15:39):null,"n",S?(Hz?hz:club):hz));
    if (P||S) rows.push(r("repl","inc","",null,"y",P?op:sSrc));
    else rows.push(r("repl","ns",L("Not mentioned","לא מוזכר"),null,"n",hz));
    rows.push(r("tow", S||P?"inc":"ns", "", null, S||P?"y":"n", P?op:sSrc));
    if (P) rows.push(r("wash","opt","",ad(7),"n",op));
    if (S) rows.push(r("driver","opt",Hz?L("₪100 / ₪29 per mo (club)","₪100 / ₪29 לחודש (מועדון)"):L("₪129 / ₪45 per mo","₪129 / ₪45 לחודש"), Hz?100:129,"n",Hz?hz:club));
    else if (P) rows.push(r("driver","opt","",ad(0),"n",op));
    else rows.push(r("driver","opt",L("Extra charge; amount not stated","בתוספת תשלום; הסכום לא צוין"),null,"n",hz));
    if (c.excessYr!=null && c.excessKm>0) rows.push(r("xkm","sep",L("Your assumed rate","התעריף שהנחת"),c.excessYr/12,"y",cmpd,c.excessYr*(T/12)));
    else rows.push(r("xkm","ns",L("Rate not published by the lessor","התעריף לא פורסם על ידי החברה"),null,"n",sSrc));
    if (S && !Hz) rows.push(r("buy","inc",L("12% off list price at end","12% הנחה ממחיר המחירון בסוף"),null,"n",dp));
    else rows.push(r("buy","ns",L("Price not stated","המחיר לא צוין"),null,"n",sSrc));
    return rows;
  }

  function chips(o,c,inp){
    const rows = comps(o,c,inp);
    return CHIP_IDS.map(([id,en,he]) => {
      const rw = rows.find(r => r.id===id);
      const lab = HE()?he:en;
      const extra = (rw && rw.id==="lic" && rw.st==="sep" && rw.pm!=null) ? " "+nis(rw.pm*12)+L("/yr"," לשנה") : "";
      return lab+" "+(rw?stMark(rw.st):"?")+extra;
    }).join(" · ");
  }

  function groups(inp){
    const map = new Map();
    for (const o of DATA.offers){
      if (state.co!=="all" && o.co!==state.co) continue;
      if (state.ch!=="all" && o.ch!==state.ch) continue;
      if (state.fuel!=="all" && (PT[o.fuel]||o.fuel)!==state.fuel && o.fuel!==state.fuel) continue;
      const hay = (nameOf(o)+" "+o.model+" "+o.make+" "+(o.canon?(o.canon.make+" "+o.canon.model+" "+o.canon.trim):"")).toLowerCase();
      if (state.q && !hay.includes(state.q.toLowerCase())) continue;
      const k = grpKey(o);
      if (!map.has(k)){
        const c = cn(o);
        map.set(k, {key:k, make:c.make, model:c.model, trim:c.trim, pt:c.pt, name:nameOf(o), subs:[]});
      }
      const calcR = calc(o, inp);
      map.get(k).subs.push({o, c:calcR});
    }
    const out = [...map.values()];
    for (const g of out){
      const priced = g.subs.filter(s => s.c[state.sortKey] != null);
      g.best = priced.length ? priced.reduce((a,b) => {
        const av=a.c[state.sortKey], bv=b.c[state.sortKey];
        return (state.dir==="asc" ? av<bv : av>bv) ? a : b;
      }) : null;
      g.sortVal = g.best ? g.best.c[state.sortKey] : (state.dir==="asc"?Infinity:-Infinity);
      if (state.sortKey==="model") g.sortVal = g.name;
    }
    out.sort((a,b) => {
      if (typeof a.sortVal==="string") return a.sortVal.localeCompare(b.sortVal) * (state.dir==="asc"?1:-1);
      if (a.sortVal===b.sortVal) return a.name.localeCompare(b.name);
      return (a.sortVal-b.sortVal) * (state.dir==="asc"?1:-1);
    });
    return out;
  }

  function el(html){ const d=document.createElement("div"); d.innerHTML=html; return d; }
  function esc(s){ return String(s??"").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

  function fmtDelta(d){
    if (!d || d.old==null || d.new==null) return "–";
    const cls = d.delta<0?"delta-down":(d.delta>0?"delta-up":"");
    const pct = d.pct==null?"":(" ("+((d.pct>0?"+":"")+d.pct.toFixed(1))+"%)");
    return `<span class="${cls}">${esc(nis(d.old))} → ${esc(nis(d.new))} ${esc(signed(d.delta))}${esc(pct)}</span>`;
  }

  function setLang(lang){
    state.lang = lang;
    try { localStorage.setItem("leaseLang", lang); } catch(e){}
    document.documentElement.lang = lang==="he"?"he":"en";
    document.documentElement.dir = lang==="he"?"rtl":"ltr";
    document.title = L("Private leasing: Shlomo Sixt, Pery and HTZone deals","ליסינג פרטי: עסקאות שלמה SIXT, פרי ו-HTZone");
    render();
  }

  function header(){
    const offers = DATA.offers;
    const sh = offers.filter(o=>o.co==="Shlomo Sixt"&&o.ch==="Direct").length;
    const p = offers.filter(o=>o.co==="Pery").length;
    const h = offers.filter(o=>o.ch==="HTZone");
    const hS=h.filter(o=>o.co==="Shlomo Sixt").length, hA=h.filter(o=>o.co==="Albar").length;
    $("lang-toggle").innerHTML = `<button type="button" aria-selected="${HE()}">עברית</button><button type="button" aria-selected="${!HE()}">English</button>`;
    $("lang-toggle").querySelectorAll("button")[0].onclick = () => setLang("he");
    $("lang-toggle").querySelectorAll("button")[1].onclick = () => setLang("en");
    $("title").textContent = L("Private leasing: Shlomo Sixt, Pery and HTZone deals","ליסינג פרטי: עסקאות שלמה SIXT, פרי ו-HTZone");
    $("summary").textContent = HE()
      ? (`כל ${offers.length} הצעות הליסינג הפרטי הנוכחיות: ${sh} של שלמה SIXT ו-${p} של פרי ישירות, ועוד ${h.length} הצעות מועדון ב-HTZone (${hS} של שלמה SIXT, ${hA} של אלבר). עמודות שמסומנות "מחושב" מחושבות לפי הנתונים שהזנת ואינן מחיר שפורסם על ידי החברות.`)
      : (`All ${offers.length} current private-lease offers: ${sh} Shlomo Sixt and ${p} Pery direct, plus ${h.length} HTZone club offers (${hS} Shlomo Sixt, ${hA} Albar). Columns marked computed are calculated from your inputs, not quoted by the lessors.`);
    const d = DATA.dates || {};
    $("updated").textContent = L("Last updated: ","עודכן לאחרונה: ") + (d.current || "") + L(" (Asia/Jerusalem). Site: "," (שעון ישראל). האתר: ") + "https://ofirr-op.github.io/leasing-deals/";
  }

  function toc(){
    const items = [
      ["price-drops", L("Price drops","ירידות מחיר")],
      ["price-history", L("Price history","היסטוריית מחיר")],
      ["new-removed", L("New and removed offers","הצעות חדשות ושהוסרו")],
      ["assumptions", L("Your assumptions","ההנחות שלך")],
      ["offers", L("All offers","כל ההצעות")],
      ["details", L("Offer details","פרטי ההצעה")],
      ["included", L("What's included, by provider","מה כלול, לפי חברה")],
      ["terms", L("Contract terms","תנאי החוזים")],
      ["htz-vs", L("HTZone deals vs direct","עסקאות HTZone מול ישיר")],
      ["how", L("How the numbers are computed","איך מחושבים המספרים")],
      ["gaps", L("Gaps","פערים")],
      ["sources", L("Sources","מקורות")]
    ];
    $("toc").innerHTML = items.map(([id,lab]) => `<a href="#${id}">${esc(lab)}</a>`).join("");
  }

  function renderDrops(){
    const ch = DATA.changes || {};
    const drops = ch.drops || [];
    const host = $("price-drops");
    let html = `<h2>${esc(L("Price drops","ירידות מחיר"))}</h2>`;
    if (drops.length){
      html += `<p>${esc(L("Changes since "+(ch.previous_date||"the previous snapshot")+".","שינויים מאז "+(ch.previous_date||"הצילום הקודם")+"." ))}</p>`;
      html += dropTable(drops);
    } else {
      html += `<p>${esc(L("No price drops since the previous snapshot"+(ch.previous_date? " ("+ch.previous_date+")":"")+".","אין ירידות מחיר מאז הצילום הקודם"+(ch.previous_date?" ("+ch.previous_date+")":"")+"."))}</p>`;
      const last = DATA.last_drops;
      if (last && last.drops && last.drops.length){
        html += `<p>${esc(L("Most recent drops (","הירידות האחרונות (") + last.current_date + L(", vs "," לעומת ") + last.previous_date + "):")}</p>`;
        html += dropTable(last.drops);
      }
    }
    const inc = ch.increases || [];
    if (inc.length){
      html += `<h3 class="kicker">${esc(L("Price increases","עליות מחיר"))}</h3>` + dropTable(inc);
    }
    host.innerHTML = html;
  }
  function dropTable(rows){
    const cols = [L("Model","דגם"),L("Provider / channel","חברה / ערוץ"),L("Monthly","חודשי"),L("Advance","מקדמה"),L("Computed total (defaults)","סך מחושב (ברירות מחדל)"),L("Deal","עסקה")];
    return `<div class="table-wrap"><table><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${
      rows.map(r => `<tr><td>${esc(r.name)}</td><td>${esc(tr(r.co))} · ${esc(tr(r.ch))}</td><td>${fmtDelta(r.monthly)}</td><td>${fmtDelta(r.advance)}</td><td>${fmtDelta(r.total)}</td><td>${r.url?`<a href="${esc(r.url)}" rel="noopener" target="_blank">${esc(L("Open","פתח"))}</a>`:"–"}</td></tr>`).join("")
    }</tbody></table></div>`;
  }

  function renderNewRemoved(){
    const ch = DATA.changes || {};
    const neu = ch.new || [], rem = ch.removed || [];
    let html = `<h2>${esc(L("New and removed offers","הצעות חדשות ושהוסרו"))}</h2>`;
    if (!neu.length && !rem.length){
      html += `<p>${esc(L("No offers were added or removed since the previous snapshot.","לא נוספו ולא הוסרו הצעות מאז הצילום הקודם."))}</p>`;
    } else {
      if (neu.length){
        html += `<div class="callout new"><strong>${esc(L("New","חדש"))}</strong><ul class="list">${neu.map(r=>`<li>${esc(r.name)} · ${esc(tr(r.co))} · ${esc(tr(r.ch))}${r.mo!=null?" · "+nis(r.mo)+L("/mo"," לחודש"):""}${r.url?` · <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(L("link","קישור"))}</a>`:""}</li>`).join("")}</ul></div>`;
      }
      if (rem.length){
        html += `<div class="callout up"><strong>${esc(L("Removed","הוסרו"))}</strong><ul class="list">${rem.map(r=>`<li>${esc(r.name)} · ${esc(tr(r.co))} · ${esc(tr(r.ch))}${r.mo!=null?" · "+nis(r.mo)+L("/mo"," לחודש"):""}</li>`).join("")}</ul></div>`;
      }
    }
    $("new-removed").innerHTML = html;
  }

  function renderAssumptions(){
    const note = (DATA.copy && DATA.copy.defaults_note) ? (HE()?DATA.copy.defaults_note.he:DATA.copy.defaults_note.en) : "";
    $("assumptions").innerHTML = `<h2>${esc(L("Your assumptions","ההנחות שלך"))}</h2>
      <div class="grid" id="inp-grid">
        ${inp("km", L("Yearly km","ק\"מ שנתי"), "number")}
        ${inp("petrol", L("Petrol 95 ₪/L","בנזין 95 ₪/ל'"), "number")}
        ${inp("diesel", L("Diesel ₪/L (unregulated; enter yours)","סולר ₪/ל' (לא מפוקח; הזן משלך)"), "number")}
        ${inp("elec", L("Electricity ₪/kWh","חשמל ₪/קוט\"ש"), "number")}
        ${inp("infl", L("Annual inflation %","אינפלציה שנתית %"), "number")}
        ${inp("xRate", L("Assumed excess-km ₪/km","ק\"מ עודף ₪/ק\"מ (הנחה)"), "number")}
      </div>
      <div class="grid" style="margin-top:.6rem">
        ${tog("shDisc", L("Apply Shlomo ₪3,000 online discount","החל את הנחת ₪3,000 של שלמה באונליין"))}
        ${tog("cmp", L("Comparable totals: add Pery maintenance add-on; use Pery's licensing add-on instead of the official fee","סכומים בני השוואה: הוסף לפרי חבילת טיפולים; השתמש בתוספת האגרה של פרי במקום האגרה הרשמית"))}
      </div>
      <p class="legend">${esc(note)}</p>`;
    bindInputs();
  }
  function inp(key, label, type){
    return `<label>${esc(label)}<input type="${type}" id="inp-${key}" value="${esc(state[key])}"></label>`;
  }
  function tog(key, label){
    return `<label class="toggle"><input type="checkbox" id="inp-${key}" ${state[key]?"checked":""}> ${esc(label)}</label>`;
  }
  function bindInputs(){
    ["km","petrol","diesel","elec","infl","xRate"].forEach(k => {
      const n = $("inp-"+k); if (!n) return;
      n.addEventListener("input", () => { state[k]=n.value; renderOffersAndDetails(); });
    });
    ["shDisc","cmp"].forEach(k => {
      const n = $("inp-"+k); if (!n) return;
      n.addEventListener("change", () => { state[k]=n.checked; if(k==="cmp") state.peryMaint=n.checked; renderOffersAndDetails(); });
    });
  }

  function offerCell(sub, best){
    if (!sub) return "–";
    const {o,c} = sub;
    const star = best && best.o.key===o.key ? `<span class="star">★</span> ` : "";
    const flag = (c.flags||[]).some(f => f==="no official consumption") ? " *" : "";
    const mo = o.mo==null?ns():((o.co==="Albar"?L("from ","החל מ-"):"")+nis(o.mo));
    const adv = o.adv==null?ns():nis(o.adv);
    const tot = c.effNom==null?ns():nis(c.effNom)+L("/mo eff."," לחודש אפקטיבי");
    return `<div class="cell-offer">${star}<span class="price">${esc(adv)} / ${esc(mo)}</span><span>${esc(tot)}${flag}</span><span class="chips">${esc(chips(o,c,inputs()))}</span></div>`;
  }

  function renderOffersAndDetails(){
    const inp = inputs();
    const gs = groups(inp);
    const fuels = ["all", ...new Set(DATA.offers.map(o => PT[o.fuel]||o.fuel))];
    const views = [["offer",L("Offer & price","הצעה ומחיר")],["running",L("Energy & km","אנרגיה וק\"מ")],["inflation",L("Inflation","אינפלציה")],["terms",L("Surcharges & terms","תוספות ותנאים")]];
    const sorts = [["effNom",L("Effective monthly (nominal)","חודשי אפקטיבי (נומינלי)")],["effInf",L("Effective monthly (infl.)","חודשי אפקטיבי (אינפלציה)")],["totalNom",L("Total nominal","סך נומינלי")],["totalInf",L("Total infl.-adj.","סך מותאם אינפלציה")],["lease",L("Lease payments only","תשלומי ליסינג בלבד")],["mo",L("Monthly (quoted)","חודשי (מפורסם)")],["adv",L("Advance","מקדמה")],["list",L("List price","מחירון")],["model",L("Model name","שם דגם")]];
    const colsOffer = [L("Model","דגם"),L("Powertrain","הנעה"),L("Shlomo direct","שלמה ישיר"),L("Shlomo via HTZone","שלמה ב-HTZone"),L("Pery","פרי"),L("Albar via HTZone","אלבר ב-HTZone")];

    $("offers").innerHTML = `<h2>${esc(L("All offers","כל ההצעות"))}</h2>
      <div class="filters">
        <label>${esc(L("Provider","חברה"))}<select id="f-co">${[["all",L("All providers","כל החברות")],["Shlomo Sixt","Shlomo Sixt"],["Pery","Pery"],["Albar","Albar"]].map(([v,l])=>`<option value="${v}" ${state.co===v?"selected":""}>${esc(l)}</option>`).join("")}</select></label>
        <label>${esc(L("Channel","ערוץ"))}<select id="f-ch">${[["all",L("All channels","כל הערוצים")],["Direct",L("Direct","ישיר")],["HTZone","HTZone"]].map(([v,l])=>`<option value="${v}" ${state.ch===v?"selected":""}>${esc(l)}</option>`).join("")}</select></label>
        <label>${esc(L("Powertrain","הנעה"))}<select id="f-fuel">${fuels.map(f=>`<option ${state.fuel===f?"selected":""}>${esc(f==="all"?L("All powertrains","כל סוגי ההנעה"):f)}</option>`).join("")}</select></label>
        <label>${esc(L("Sort by","מיון"))}<select id="f-sort">${sorts.map(([v,l])=>`<option value="${v}" ${state.sortKey===v?"selected":""}>${esc(l)}</option>`).join("")}</select></label>
        <label>${esc(L("Order","סדר"))}<select id="f-dir"><option value="asc" ${state.dir==="asc"?"selected":""}>${esc(L("Low → high","נמוך → גבוה"))}</option><option value="desc" ${state.dir==="desc"?"selected":""}>${esc(L("High → low","גבוה → נמוך"))}</option></select></label>
        <label>${esc(L("Search make or model","חיפוש יצרן או דגם"))}<input type="search" id="f-q" value="${esc(state.q)}" placeholder="Kona, BYD, טוסון"></label>
      </div>
      <div class="seg" id="f-view">${views.map(([v,l])=>`<button type="button" data-v="${v}" aria-selected="${state.view===v}">${esc(l)}</button>`).join("")}</div>
      <div class="table-wrap" style="margin-top:.7rem"><table><thead><tr>${colsOffer.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${gs.map(g => {
        const by = {sd:null,sh:null,pd:null,ah:null};
        g.subs.forEach(s => by[slotOf(s.o)] = s);
        const label = esc(g.name)+(g.subs[0]&&g.subs[0].c.flags.some(f=>f==="no official consumption")?" *":"");
        const chartBtn = (window.PRICE_HISTORY && (window.PRICE_HISTORY.models||[]).some(m => m.id===g.key))
          ? `<button type="button" class="btn chart-btn" data-model="${esc(g.key)}">${esc(L("Price chart","גרף מחיר"))}</button>` : "";
        const cells = ["sd","sh","pd","ah"].map(sl => `<td>${offerCell(by[sl], g.best)}</td>`);
        const first = g.subs[0];
        const clickKey = (g.best||first).o.key;
        return `<tr data-key="${esc(clickKey)}" class="${state.sel===clickKey||g.subs.some(s=>s.o.key===state.sel)?"active":""}"><td><strong>${label}</strong>${cn(first.o).variant?`<div class="muted">${esc(varName(cn(first.o).variant))}</div>`:""}${chartBtn}</td><td>${esc(tr(g.pt))}</td>${cells.join("")}</tr>`;
      }).join("")}</tbody></table></div>
      <p class="legend">${esc((DATA.copy&&DATA.copy.legend)?(HE()?DATA.copy.legend.he:DATA.copy.legend.en):"")}
      ${esc(HE()? (gs.length+" שורות של דגם ורמת גימור, "+gs.reduce((n,g)=>n+g.subs.length,0)+" הצעות. ★ = התשלום האפקטיבי הנמוך ביותר לפי ההנחות שלך.") : (gs.length+" model+trim rows, "+gs.reduce((n,g)=>n+g.subs.length,0)+" offers. ★ = lowest effective monthly at your inputs."))}</p>`;

    $("f-co").onchange = e => { state.co=e.target.value; renderOffersAndDetails(); };
    $("f-ch").onchange = e => { state.ch=e.target.value; renderOffersAndDetails(); };
    $("f-fuel").onchange = e => { state.fuel=e.target.value==="all"||e.target.selectedIndex===0?"all":e.target.value; renderOffersAndDetails(); };
    $("f-sort").onchange = e => { state.sortKey=e.target.value; renderOffersAndDetails(); };
    $("f-dir").onchange = e => { state.dir=e.target.value; renderOffersAndDetails(); };
    $("f-q").oninput = e => { state.q=e.target.value; renderOffersAndDetails(); };
    $("f-view").onclick = e => { const b=e.target.closest("button"); if(!b) return; state.view=b.dataset.v; renderOffersAndDetails(); };
    $("offers").querySelectorAll("tbody tr").forEach(tr => {
      tr.addEventListener("click", (ev) => {
        const chart = ev.target.closest(".chart-btn");
        if (chart) {
          ev.stopPropagation();
          showModelChart(chart.getAttribute("data-model"));
          return;
        }
        state.sel = tr.getAttribute("data-key");
        renderOffersAndDetails();
        $("details").scrollIntoView({behavior:"smooth",block:"start"});
      });
    });

    renderDetails(inp, gs);
  }

  function renderDetails(inp){
    const o = DATA.offers.find(x => x.key===state.sel) || DATA.offers[0];
    if (!o){ $("details").innerHTML=""; return; }
    const c = calc(o,inp);
    const rows = comps(o,c,inp);
    const others = DATA.offers.filter(x => grpKey(x)===grpKey(o) && x.key!==o.key);
    const cname2 = id => HE()?CNAME[id][1]:CNAME[id][0];
    const inTLabel = s => s==="y"?L("Yes","כן"):s==="i"?L("Inflation-adj. total only","רק בסך המותאם לאינפלציה"):s==="-"?"–":L("No","לא");
    const sel = `<label>${esc(L("Offer","הצעה"))}<select id="d-sel">${DATA.offers.map(x=>`<option value="${esc(x.key)}" ${x.key===o.key?"selected":""}>${esc(nameOf(x)+" · "+tr(x.co)+" · "+tr(x.ch))}</option>`).join("")}</select></label>`;
    const props = [
      [L("Provider / channel","חברה / ערוץ"), tr(o.co)+" · "+(o.ch==="HTZone"?L("via HTZone club offer","דרך הצעת מועדון ב-HTZone"):L("direct from the lessor's site","ישירות מאתר החברה"))],
      [L("Model / trim / powertrain","דגם / רמת גימור / הנעה"), nameOf(o)+" · "+tr(cn(o).pt)+(cn(o).variant?" · "+varName(cn(o).variant):"")],
      [L("Source title (as listed)","כותרת המקור (כפי שפורסמה)"), o.make+" · "+o.model],
      [L("Model year","שנת דגם"), o.year!=null?String(o.year):ns()],
      [L("Importer list price","מחיר מחירון יבואן"), o.list!=null?nis(o.list):ns()],
      [L("Advance","מקדמה"), o.adv!=null?nis(o.adv)+(o.advReg!=null?L(" (HTZone club; regular "+nis(o.advReg)+")"," (מועדון HTZone; רגיל "+nis(o.advReg)+")"):""):ns()],
      [L("Monthly (20,000 km/yr)","תשלום חודשי (20,000 ק\"מ בשנה)"), o.mo!=null?((o.co==="Albar"?L("from ","החל מ-"):"")+nis(o.mo)):ns()],
      [L("Term / included km","תקופה / ק\"מ כלולים"), o.term+L(" months · "," חודשים · ")+(o.key==="H-166284"?L("km quota not stated","מכסת ק\"מ לא צוינה"):INCLUDED_KM.toLocaleString("en-US")+L(" km/yr"," ק\"מ בשנה"))],
      [L("Computed total nominal / infl.-adj.","סך מחושב נומינלי / מותאם אינפלציה"), (c.totalNom!=null?nis(c.totalNom):ns())+" / "+(c.totalInf!=null?nis(c.totalInf):ns())],
      [L("Effective monthly nominal / infl.-adj.","חודשי אפקטיבי נומינלי / מותאם אינפלציה"), (c.effNom!=null?nis(c.effNom):ns())+" / "+(c.effInf!=null?nis(c.effInf):ns())],
      [L("Consumption (WLTP)","צריכה (WLTP)"), o.kwh!=null?o.kwh+L(" kWh/100 km"," קוט\"ש/100 ק\"מ"):(o.l100!=null?o.l100.toFixed(2)+L(" L/100 km"," ל'/100 ק\"מ"):ns())],
      [L("Registry entry","רשומת מאגר"), o.reg||ns()],
      [L("Caveats","הסתייגויות"), c.flags.length?c.flags.map(tr).join(" · "):L("none","אין")],
      [L("Deal page","עמוד העסקה"), o.url]
    ];
    $("details").innerHTML = `<h2>${esc(L("Offer details","פרטי ההצעה"))}</h2>${sel}
      <dl class="props">${props.map(([k,v]) => `<dt>${esc(k)}</dt><dd>${k===L("Deal page","עמוד העסקה")&&o.url?`<a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.url)}</a>`:esc(v)}</dd>`).join("")}</dl>
      <div class="table-wrap" style="margin-top:1rem"><table><thead><tr>${[L("Component","מרכיב"),L("Status","סטטוס"),L("Note","הערה"),L("Monthly","לחודש"),L("Over the term","על פני התקופה"),L("In the total?","בסך?"),L("Source","מקור")].map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(rw=>`<tr><td>${esc(cname2(rw.id))}</td><td>${esc(stLab(rw.id,rw.st))}</td><td>${esc(rw.note||"")}</td><td>${rw.pm!=null?esc(nis(rw.pm)):"–"}</td><td>${rw.tot!=null?esc(nis(rw.tot)):"–"}</td><td>${esc(inTLabel(rw.inT))}</td><td>${esc(rw.src||"")}</td></tr>`).join("")}</tbody></table></div>
      ${others.length?`<p class="legend">${esc(L("Same model, other channels:","אותו דגם בערוצים אחרים:"))} ${others.map(x=>esc(tr(x.co)+" · "+tr(x.ch)+(x.mo!=null?" · "+nis(x.mo):""))).join(" · ")}</p>`:""}`;
    const selEl = $("d-sel");
    if (selEl) selEl.onchange = e => { state.sel=e.target.value; renderOffersAndDetails(); };
  }

  function renderStatic(){
    const licRows = (LIC.fee_up_to_3_years||[]).map((f,i) => {
      const bands=LIC.bands||[];
      const lim = i===0? L("up to ","עד ")+nis(bands[0]) : i===6? L("over ","מעל ")+nis(bands[5]) : ISO(nis(bands[i-1]+1)+"–"+nis(bands[i]));
      return `<tr><td>${i+1}</td><td>${esc(lim)}</td><td>${esc(nis(f))}</td><td>${esc(nis(f+LIC.broadcasting_levy))}</td></tr>`;
    }).join("");
    const copy = (k) => { const c=DATA.copy&&DATA.copy[k]; return c?(HE()?c.he:c.en):""; };
    $("included").innerHTML = `<h2>${esc(L("What's included, by provider","מה כלול, לפי חברה"))}</h2><p>${esc(copy("included_by_provider"))}</p>
      <p>${esc(copy("licensing"))}</p>
      <div class="table-wrap"><table><thead><tr>${[L("Price group","קבוצת מחיר"),L("List price (2026 limits)","מחיר מחירון (גבולות 2026)"),L("Fee, up to 3 years old","אגרה, עד 3 שנים"),L("With ₪135 broadcasting levy","כולל ₪135 לתאגיד השידור")].map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${licRows}</tbody></table></div>`;
    $("terms").innerHTML = `<h2>${esc(L("Contract terms","תנאי החוזים"))}</h2>
      <h3>${esc(L("Shlomo Sixt","שלמה SIXT"))}</h3><p>${esc(copy("shlomo_terms"))}</p>
      <h3>Pery</h3><p>${esc(copy("pery_terms"))}</p>
      <h3>${esc(L("Albar (via HTZone)","אלבר (דרך HTZone)"))}</h3><p>${esc(copy("albar_terms"))}</p>`;
    $("how").innerHTML = `<h2>${esc(L("How the numbers are computed","איך מחושבים המספרים"))}</h2><p>${esc(copy("how"))}</p>`;
    $("gaps").innerHTML = `<h2>${esc(L("Gaps","פערים"))}</h2><p>${esc(copy("gaps"))}</p>`;
    const srcs = DATA.sources_list || [];
    $("sources").innerHTML = `<h2>${esc(L("Sources","מקורות"))}</h2><ul class="list">${srcs.map(s=>`<li><a href="${esc(s.href)}" target="_blank" rel="noopener">${esc(HE()?s.title.he:s.title.en)}</a> · ${esc(s.site)}</li>`).join("")}</ul>`;
    $("footer").innerHTML = `<p>${esc(L("Generated from the public catalogs of Shlomo Sixt, Pery and HTZone. Code and daily snapshots: ","נוצר מקטלוגים פומביים של שלמה SIXT, פרי ו-HTZone. הקוד והצילומים היומיים: "))}<a href="https://github.com/ofirr-op/leasing-deals">github.com/ofirr-op/leasing-deals</a>. ${esc(L("Published at ","מפורסם ב-"))}<a href="https://ofirr-op.github.io/leasing-deals/">ofirr-op.github.io/leasing-deals</a>.</p>`;
    renderHtzVs();
  }

  function renderHtzVs(){
    const inp = inputs();
    const htz = DATA.offers.filter(o => o.ch==="HTZone");
    const rows = htz.map(h => {
      const same = DATA.offers.find(d => d.ch==="Direct" && d.co===h.co && grpKey(d)===grpKey(h));
      const hc=calc(h,inp), sc=same?calc(same,inp):null;
      return `<tr><td>${esc(nameOf(h))} ${esc(tr(cn(h).pt))}</td><td>${esc(tr(h.co))}</td>
        <td>${esc((h.adv!=null?nis(h.adv):ns())+" / "+(h.mo!=null?(h.co==="Albar"?L("from ","החל מ-"):"")+nis(h.mo):ns()))}</td>
        <td>${same?esc((same.adv!=null?nis(same.adv):ns())+" / "+(same.mo!=null?nis(same.mo):ns())):esc(L("No direct listing","אין מודעה ישירה"))}</td>
        <td>${same&&same.adv!=null&&h.adv!=null?esc(signed(h.adv-same.adv)):"–"}</td>
        <td>${same&&same.mo!=null&&h.mo!=null?esc(signed(h.mo-same.mo)):"–"}</td>
        <td>${sc&&sc.lease!=null&&hc.lease!=null?esc(signed(hc.lease-sc.lease)):"–"}</td></tr>`;
    }).join("");
    $("htz-vs").innerHTML = `<h2>${esc(L("HTZone deals vs direct","עסקאות HTZone מול ישיר"))}</h2>
      <div class="table-wrap"><table><thead><tr>${[L("Model","דגם"),L("Provider","חברה"),L("HTZone advance / monthly","HTZone מקדמה / חודשי"),L("Direct advance / monthly","ישיר מקדמה / חודשי"),L("Advance Δ","Δ מקדמה"),L("Monthly Δ","Δ חודשי"),L("Lease-payments Δ","Δ תשלומי ליסינג")].map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function historyData(){ return window.PRICE_HISTORY || null; }

  function modelLabel(m){
    if (!m) return "";
    const bits = HE()
      ? [heOf(DATA.canonical.make_he, m.make), heOf(DATA.canonical.model_he, m.model), heOf(DATA.canonical.trim_he, m.trim)]
      : [m.make, m.model, m.trim];
    const name = bits.filter(Boolean).join(" ");
    return m.pt ? name + " · " + tr(m.pt) : name;
  }

  function companyLabel(c){ return HE() ? c.he : c.en; }

  function defaultChartModel(){
    const H = historyData();
    if (!H || !H.models || !H.models.length) return "";
    const o = DATA.offers.find(x => x.key===state.sel);
    if (o && H.models.some(m => m.id===grpKey(o))) return grpKey(o);
    return H.models[0].id;
  }

  function seriesValues(list, n){
    const arr = Array(n).fill(null);
    (list || []).forEach(([i, eff, mo]) => {
      if (i >= 0 && i < n && eff != null) arr[i] = {y: eff, mo: mo};
    });
    return arr;
  }

  function niceStep(span, count){
    const rough = span / Math.max(1, count);
    if (!isFinite(rough) || rough <= 0) return 1;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const err = rough / pow;
    const f = err <= 1 ? 1 : err <= 2 ? 2 : err <= 5 ? 5 : 10;
    return f * pow;
  }

  function axisScale(values){
    let min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    if (min === max) { min -= 100; max += 100; }
    const step = niceStep(max - min, 4);
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step || lo + step;
    const nTicks = Math.max(1, Math.round((hi - lo) / step));
    const ticks = [];
    for (let i = 0; i <= nTicks; i++) ticks.push(lo + i * step);
    return {lo, hi: lo === hi ? lo + step : hi, ticks};
  }

  function mountLineChart(host, datasets){
    const H = historyData();
    const scans = (H && H.scans) || [];
    if (host._chartAbort) host._chartAbort.abort();
    host.innerHTML = "";
    const usable = datasets.filter(ds => (ds.values || []).some(v => v && v.y != null));
    if (!scans.length || !usable.length){
      host.innerHTML = `<p class="muted">${esc(L("No prices for this chart yet.","אין עדיין מחירים לגרף הזה."))}</p>`;
      return;
    }
    const ys = [];
    usable.forEach(ds => ds.values.forEach(v => { if (v && v.y != null) ys.push(v.y); }));
    const scale = axisScale(ys);
    const W = 720, Ht = 280;
    const pad = {l: 78, r: 18, t: 12, b: 40};
    const iw = W - pad.l - pad.r, ih = Ht - pad.t - pad.b;
    const n = scans.length;
    const xOf = i => pad.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
    const yOf = v => pad.t + ((scale.hi - v) / (scale.hi - scale.lo)) * ih;
    const NS = "http://www.w3.org/2000/svg";
    const plot = document.createElement("div");
    plot.className = "chart-plot";
    plot.dir = "ltr";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + Ht);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", L("Effective price by date","מחיר אפקטיבי לפי תאריך"));
    const abort = new AbortController();
    host._chartAbort = abort;
    const listen = { signal: abort.signal };
    function svgEl(name, attrs){
      const node = document.createElementNS(NS, name);
      Object.keys(attrs).forEach(k => node.setAttribute(k, attrs[k]));
      return node;
    }
    scale.ticks.forEach(t => {
      const y = yOf(t);
      svg.appendChild(svgEl("line", {x1: pad.l, x2: W - pad.r, y1: y, y2: y, stroke: "#e4ddd3", "stroke-width": "1"}));
      const tx = svgEl("text", {x: pad.l - 8, y: y + 4, "text-anchor": "end", fill: "#5c564e", "font-size": "12"});
      tx.textContent = "₪" + Math.round(t).toLocaleString("en-US");
      svg.appendChild(tx);
    });
    const labelStep = Math.max(1, Math.ceil(n / 6));
    scans.forEach((s, i) => {
      if (i % labelStep !== 0 && i !== n - 1) return;
      const anchor = n > 1 && i === 0 ? "start" : n > 1 && i === n - 1 ? "end" : "middle";
      const tx = svgEl("text", {x: xOf(i), y: Ht - 14, "text-anchor": anchor, fill: "#5c564e", "font-size": "12"});
      tx.textContent = s.label;
      svg.appendChild(tx);
    });
    const hits = [];
    usable.forEach(ds => {
      let d = "", pen = false;
      ds.values.forEach((v, i) => {
        if (!v || v.y == null) { pen = false; return; }
        d += (pen ? "L" : "M") + xOf(i).toFixed(1) + " " + yOf(v.y).toFixed(1) + " ";
        pen = true;
      });
      if (d) svg.appendChild(svgEl("path", {d: d, fill: "none", stroke: ds.color, "stroke-width": "2.5", "stroke-linejoin": "round", "stroke-linecap": "round"}));
      ds.values.forEach((v, i) => {
        if (!v || v.y == null) return;
        svg.appendChild(svgEl("circle", {cx: xOf(i), cy: yOf(v.y), r: 4.5, fill: ds.color, stroke: "#fffdf9", "stroke-width": "1.5"}));
        hits.push({x: xOf(i), y: yOf(v.y), v: v, ds: ds, i: i});
      });
    });
    plot.appendChild(svg);
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    plot.appendChild(tip);
    host.appendChild(plot);

    const legend = document.createElement("ul");
    legend.className = "chart-legend";
    usable.forEach(ds => {
      const li = document.createElement("li");
      li.innerHTML = `<i style="background:${esc(ds.color)}"></i>${esc(ds.label)}`;
      legend.appendChild(li);
    });
    host.appendChild(legend);

    const rows = [];
    scans.forEach((s, i) => {
      usable.forEach(ds => {
        const v = ds.values[i];
        if (!v || v.y == null) return;
        rows.push(`<tr><td>${esc(s.tip || s.label)}</td><td>${esc(ds.label)}</td><td>${esc(v.model || "")}</td><td>${esc(nis(v.y))}</td><td>${v.mo == null ? "–" : esc(nis(v.mo))}</td></tr>`);
      });
    });
    const table = document.createElement("details");
    table.className = "chart-data";
    table.innerHTML = `<summary>${esc(L("Numbers","המספרים"))}</summary><div class="table-wrap"><table><thead><tr>${
      [L("Date","תאריך"), L("Company","חברה"), L("Model","דגם"), L("Effective","אפקטיבי"), L("Monthly","חודשי")].map(c => `<th>${esc(c)}</th>`).join("")
    }</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    host.appendChild(table);

    function showTip(clientX, clientY, h){
      const scan = scans[h.i];
      const lines = [
        `<div>${esc(scan.tip || scan.label)}</div>`,
        `<div><i style="background:${esc(h.ds.color)};display:inline-block;width:.65rem;height:.65rem;border-radius:99px;margin-inline-end:.35rem"></i>${esc(h.ds.label)}</div>`
      ];
      if (h.v.model) lines.push(`<div>${esc(h.v.model)}</div>`);
      lines.push(`<div>${esc(L("Effective","אפקטיבי"))} ${esc(nis(h.v.y))}</div>`);
      if (h.v.mo != null) lines.push(`<div>${esc(L("Monthly","חודשי"))} ${esc(nis(h.v.mo))}</div>`);
      tip.dir = document.documentElement.dir || "rtl";
      tip.innerHTML = lines.join("");
      tip.hidden = false;
      const box = plot.getBoundingClientRect();
      let left = clientX - box.left + 12;
      let top = clientY - box.top - 8;
      tip.style.left = "0px";
      tip.style.top = "0px";
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      if (left + tw > box.width - 4) left = clientX - box.left - tw - 12;
      top = top - th;
      if (top < 4) top = clientY - box.top + 16;
      if (left < 4) left = 4;
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    }
    function nearest(clientX, clientY, pointerType){
      const ctm = svg.getScreenCTM();
      if (!ctm) return null;
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const p = pt.matrixTransform(ctm.inverse());
      const thresh = (pointerType === "touch" ? 36 : 22) / Math.abs(ctm.a || 1);
      let best = null, bestD = thresh;
      hits.forEach(h => {
        const d = Math.hypot(h.x - p.x, h.y - p.y);
        if (d <= bestD) { best = h; bestD = d; }
      });
      return best;
    }
    // Mouse hover follows the pointer. A tap on a phone keeps the tooltip open
    // until the next tap, because pointerleave fires as soon as the finger lifts.
    svg.addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") return;
      const h = nearest(e.clientX, e.clientY, "mouse");
      if (!h) { tip.hidden = true; return; }
      showTip(e.clientX, e.clientY, h);
    }, listen);
    svg.addEventListener("pointerdown", (e) => {
      const h = nearest(e.clientX, e.clientY, e.pointerType || "touch");
      if (!h) { tip.hidden = true; return; }
      showTip(e.clientX, e.clientY, h);
    }, listen);
    plot.addEventListener("pointerleave", (e) => {
      if (!e.pointerType || e.pointerType === "mouse") tip.hidden = true;
    }, listen);
    document.addEventListener("pointerdown", (e) => {
      if (!plot.contains(e.target)) tip.hidden = true;
    }, listen);
  }

  function overviewDatasets(){
    const H = historyData();
    const n = H.scans.length;
    const mode = state.overviewMode || "avg";
    return H.companies.map(c => {
      const values = Array(n).fill(null);
      for (let i = 0; i < n; i++){
        const pts = [];
        H.models.forEach(m => {
          const hit = (m.series[c.id] || []).find(p => p[0] === i);
          if (hit) pts.push({eff: hit[1], mo: hit[2], name: modelLabel(m)});
        });
        if (!pts.length) continue;
        if (mode === "min"){
          pts.sort((a, b) => a.eff - b.eff);
          values[i] = {y: pts[0].eff, mo: pts[0].mo, model: pts[0].name};
        } else {
          const sum = pts.reduce((s, p) => s + p.eff, 0);
          values[i] = {y: Math.round(sum / pts.length), model: L("Average of ","ממוצע של ") + pts.length + L(" models"," דגמים")};
        }
      }
      return {label: companyLabel(c), color: c.color, values};
    });
  }

  function drawOverview(){
    const host = $("chart-overview");
    if (!host || !historyData()) return;
    mountLineChart(host, overviewDatasets());
    document.querySelectorAll("#overview-mode button").forEach(b => {
      b.setAttribute("aria-selected", b.dataset.mode === (state.overviewMode || "avg") ? "true" : "false");
    });
  }

  function drawDetail(){
    const H = historyData();
    const host = $("chart-detail");
    if (!H || !host) return;
    const m = H.models.find(x => x.id === state.chartModel);
    const n = H.scans.length;
    const name = modelLabel(m);
    const datasets = H.companies.map(c => ({
      label: companyLabel(c),
      color: c.color,
      values: seriesValues(m && m.series[c.id], n).map(v => v ? Object.assign({model: name}, v) : null)
    }));
    mountLineChart(host, datasets);
  }

  function showModelChart(id){
    if (!id) return;
    state.chartModel = id;
    const sel = $("hist-model");
    if (sel) sel.value = id;
    drawDetail();
    const box = $("price-history");
    if (box) box.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function renderHistory(){
    const host = $("price-history");
    const H = historyData();
    const title = L("Effective price over time","מחיר אפקטיבי לאורך זמן");
    if (!H || !H.models || !H.models.length){
      host.innerHTML = `<h2>${esc(title)}</h2><p>${esc(L("No saved scans to chart yet.","אין עדיין סריקות שמורות לגרף."))}</p>`;
      return;
    }
    if (!state.chartModel || !H.models.some(m => m.id === state.chartModel)) state.chartModel = defaultChartModel();
    if (!state.overviewMode) state.overviewMode = "avg";
    const models = H.models.slice().sort((a, b) => modelLabel(a).localeCompare(modelLabel(b), HE() ? "he" : "en"));
    const caption = HE() ? (H.definition && H.definition.he) : (H.definition && H.definition.en);
    host.innerHTML = `<h2>${esc(title)}</h2>
      <p class="legend chart-caption">${esc(caption || "")}</p>
      <h3>${esc(L("Overview","סקירה"))}</h3>
      <div class="seg" id="overview-mode">
        <button type="button" data-mode="avg" aria-selected="${state.overviewMode === "avg"}">${esc(L("Average effective price","מחיר אפקטיבי ממוצע"))}</button>
        <button type="button" data-mode="min" aria-selected="${state.overviewMode === "min"}">${esc(L("Cheapest effective price","המחיר האפקטיבי הזול"))}</button>
      </div>
      <div class="chart-block" id="chart-overview"></div>
      <div class="hist-controls">
        <label>${esc(L("Model and trim","דגם ורמת גימור"))}
          <select id="hist-model">${models.map(m => `<option value="${esc(m.id)}" ${m.id === state.chartModel ? "selected" : ""}>${esc(modelLabel(m))}</option>`).join("")}</select>
        </label>
      </div>
      <div class="chart-block" id="chart-detail"></div>`;
    $("overview-mode").onclick = (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      state.overviewMode = b.dataset.mode;
      drawOverview();
    };
    $("hist-model").onchange = (e) => { state.chartModel = e.target.value; drawDetail(); };
    drawOverview();
    drawDetail();
  }

  function render(){
    header(); toc(); renderDrops(); renderHistory(); renderNewRemoved(); renderAssumptions(); renderOffersAndDetails(); renderStatic();
  }
  render();
})();
