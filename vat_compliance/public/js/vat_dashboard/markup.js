// Skeleton of the VAT page dashboard. data-field = text, data-slot = rendered visual,
// data-drill = drill-through key resolved in render.js.
frappe.provide("vat_compliance.page");

vat_compliance.page.HTML = () => {
	const P = `<i class="sc p" title="${__("Moves with the period")}"></i>`;
	const T = `<i class="sc t" title="${__("As of today")}"></i>`;
	const presets = [["tm", __("This month")], ["lm", __("Last month")], ["fy", __("Fiscal year")], ["1y", __("12 months")]];
	return `
<div class="cd">
<div class="hd">
  <div class="hd-mono">VAT</div>
  <div class="hd-id">
    <div class="hd-name">${__("VAT Compliance")}</div>
    <div class="hd-meta" data-field="meta">—</div>
  </div>
  <div class="hd-r">
    <div><div class="k">${T}${__("VAT balance")}</div><div class="v" data-field="hd_balance">—</div></div>
    <div><div class="k">${P}${__("Net VAT")} · <span data-field="hd_period">—</span></div><div class="v" data-field="hd_net">—</div></div>
  </div>
</div>

<div class="fc">
  <div class="fc-r1"><select class="fsel" data-f="company" aria-label="${__("Company")}"></select></div>
  <div class="fc-r2">
    <span class="lg"><span><i class="sc p"></i>${__("moves with period")}</span><span><i class="sc t"></i>${__("as of today")}</span></span>
    <div class="per" role="group" aria-label="${__("Period")}">
      ${presets.map(([p, l]) => `<button type="button" data-p="${p}">${l}</button>`).join("")}
      <button type="button" class="cu" data-p="custom" aria-haspopup="dialog">${__("Custom")}</button>
      <div class="pop" role="dialog" aria-label="${__("Custom period")}">
        <div class="dates"><label>${__("From")}<input type="date" class="from"></label><label>${__("To")}<input type="date" class="to"></label></div>
        <div class="perr"></div>
        <div class="act"><button type="button" class="cancel">${__("Cancel")}</button><button type="button" class="go">${__("Apply")}</button></div>
      </div>
    </div>
  </div>
</div>

<div data-slot="body"><div class="ld">${__("Loading VAT dashboard…")}</div></div>
</div>`;
};

vat_compliance.page.BODY = () => {
	const P = `<i class="sc p"></i>`;
	const T = `<i class="sc t"></i>`;
	const stage = (bg, key, label, drill) => `<div class="fl-c" style="--bg:${bg}"><div class="fl-k">${label}</div>
		<div class="fl-v"><a class="lk" data-field="st_${key}" data-drill="${drill}">—</a></div><div class="fl-s" data-field="st_${key}_s">—</div></div>`;
	return `
<div class="mx surf">
  <div class="mx-c">
    <div class="k">${P}${__("Output VAT")}</div>
    <div class="mx-v"><a class="lk" data-field="output" data-drill="output">—</a></div>
    <div class="mx-s"><span class="pill" data-field="output_change">—</span><span data-field="output_caption">—</span></div>
    <div class="mx-sp" data-slot="output_trend"></div>
  </div>
  <div class="mx-c">
    <div class="k">${P}${__("Input VAT")}</div>
    <div class="mx-v"><a class="lk" data-field="input" data-drill="input">—</a></div>
    <div class="mx-s"><span class="pill" data-field="input_share">—</span><span data-field="input_caption">—</span></div>
    <div class="mx-sp" data-slot="input_trend"></div>
  </div>
  <div class="mx-c tint">
    <div class="k">${P}${__("Net VAT payable")}</div>
    <div class="mx-v" data-field="net">—</div>
    <div class="mx-s"><span class="pill" data-field="net_pill">—</span><span data-field="net_caption">—</span></div>
    <div class="mx-sp" data-slot="net_trend"></div>
  </div>
  <div class="mx-c">
    <div class="k">${T}${__("VAT account balance")}</div>
    <div class="mx-v"><a class="lk" data-field="balance" data-drill="balance">—</a></div>
    <div class="mx-s" data-field="balance_caption">—</div>
    <div class="mx-sp" data-slot="balance_trend"></div>
  </div>
</div>

<div class="sec">${P}${__("Treasury status · Sales VAT & VDS Management rules")}<span class="sub" data-field="status_sub">—</span></div>
<div class="fl">
  ${stage("#22405e", "ipnr", __("Invoiced, unpaid"), "s_IPNR")}
  ${stage("#17505d", "collected", __("Collected"), "s_Collected")}
  ${stage("#0f5a4e", "cdgt", __("Deposited"), "s_CDGT")}
  ${stage("#0a5a3c", "withheld", __("Withheld by customers"), "s_DVCNR")}
  ${stage("#7a4f12", "dngt", __("VDS to deposit"), "v_DNGT")}
</div>

<div class="surf card"><div class="two">
  <div><div class="hrow"><div class="h">${__("Output vs input VAT")}</div><div class="hs" data-field="combo_sub">—</div></div>
    <div data-slot="combo"></div>
    <div class="lgd"><span><i style="background:#097C52"></i>${__("Output VAT")}</span><span><i style="background:#a3552f;height:2px"></i>${__("Input VAT")}</span></div></div>
  <div><div class="hrow"><div class="h">${__("VAT postings by source")}</div><div class="hs" data-field="mix_sub">—</div></div>
    <div data-slot="mix"></div></div>
</div></div>

<div class="surf card"><div class="two">
  <div><div class="hrow"><div class="h">${__("Top customers by output VAT")}</div><div class="hs" data-field="cust_sub">—</div></div>
    <div class="rk" data-slot="customers"></div></div>
  <div><div class="hrow"><div class="h">${__("Top suppliers by input VAT")}</div><div class="hs" data-field="supp_sub">—</div></div>
    <div class="rk" data-slot="suppliers"></div></div>
</div></div>

<div class="surf card">
  <div class="hrow"><div class="h">${__("VAT postings")}</div><div class="hs" data-field="work_sub">—</div></div>
  <div class="tb-wrap"><table class="tb">
    <thead><tr><th>${__("Date")}</th><th>${__("Document")}</th><th>${__("Source")}</th><th>${__("Party")}</th>
      <th class="n">${__("Net value")}</th><th class="n">${__("VAT")}</th><th>${__("Item tax template")}</th></tr></thead>
    <tbody data-slot="work"></tbody>
  </table></div>
  <div class="more" data-slot="work_more"></div>
</div>`;
};
