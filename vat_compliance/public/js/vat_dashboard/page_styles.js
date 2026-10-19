// Extra rules for the VAT page dashboard, layered on vat_compliance.dashboard.CSS
// (the record dashboard's stylesheet) inside the page's own shadow root.
frappe.provide("vat_compliance.page");

vat_compliance.page.CSS = `
.cd{padding:6px 2px 30px}
.hd-meta b{font-weight:500}

/* filter card: company on row 1, legend + period presets on row 2 */
.fc{background:#fff;border:1px solid var(--rule);border-radius:var(--r);padding:12px 14px 11px;margin-top:14px}
.fc-r1{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.fsel{font-family:inherit;font-size:13px;height:28px;border:0;border-radius:8px;padding:0 28px 0 9px;min-width:200px;
  background:#dceffa url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23171717' stroke-width='1.4'/%3E%3C/svg%3E") no-repeat right 10px center;
  color:#171717;appearance:none;cursor:pointer}
.fsel:focus-visible{outline:2px solid var(--steel);outline-offset:1px}
.fc-r2{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px}
.lg{flex:1 1 220px;display:flex;flex-wrap:wrap;gap:4px 12px;font-size:10.5px;color:var(--mid)}
.lg span{display:inline-flex;align-items:center}
.sc{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;flex:none}
.sc.p{background:var(--green)}
.sc.t{background:#fff;border:1px solid var(--mid)}
.k .sc{vertical-align:1px}
.per{position:relative;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px;margin-left:auto}
.per button{font-family:inherit;font-size:10.5px;font-weight:500;line-height:1.3;padding:4px 9px;border-radius:5px;
  color:var(--mid);border:1px solid var(--rule);background:#fff;cursor:pointer;white-space:nowrap}
.per button:hover{border-color:#c5ccd4;color:var(--ink)}
.per button:focus-visible{outline:2px solid #2C377D;outline-offset:1px}
.per button.on,.per button.go{background:#2C377D;border-color:#2C377D;color:#fff;font-weight:600}
.pop{display:none;position:absolute;top:calc(100% + 6px);right:0;z-index:40;width:300px;max-width:calc(100vw - 32px);padding:12px;background:#fff;
  border:1px solid var(--rule);border-radius:8px;box-shadow:0 10px 28px rgba(13,17,23,.14)}
.pop.open{display:block}
.pop .dates{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px}
.pop label{min-width:0;display:flex;flex-direction:column;gap:4px;font-size:9px;letter-spacing:.14em;text-transform:uppercase;font-weight:500;color:var(--mid)}
.pop input{font-family:inherit;font-size:12px;padding:5px 6px;border:1px solid var(--rule);border-radius:5px;color:var(--ink);width:100%;min-width:0;box-sizing:border-box}
.pop .perr{display:none;margin-top:8px;font-size:11px;color:var(--claret)}
.pop .perr.on{display:block}
.pop .act{display:flex;justify-content:flex-end;gap:6px;margin-top:10px}

.sec .sub{margin-left:auto;order:2;letter-spacing:0;text-transform:none;font-size:10.5px;font-weight:400}
.fl-c a.lk,.fl-c a.lk:hover{color:#fff}

/* donut legend + runway rows */
.dn{display:flex;align-items:center;flex-wrap:wrap;justify-content:center;gap:16px 20px}
.dn svg{width:132px;flex:none}
.dn-l{flex:1 1 200px;min-width:0;display:flex;flex-direction:column;gap:9px;font-size:12px}
.dn-r{display:grid;grid-template-columns:9px 1fr auto auto;align-items:center;gap:8px}
.dn-r i{width:8px;height:8px;border-radius:2px}
.dn-r .n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dn-r .p{color:var(--mid);font-size:11px}
.dn-r .v{font-weight:600;text-align:right;white-space:nowrap}
.dn-r.lk{cursor:pointer;border-radius:4px}
.dn-r.lk:hover .n{text-decoration:underline;text-underline-offset:3px}
.rk > div.lk{cursor:pointer}
.rk > div.lk:hover .rk-n{text-decoration:underline;text-underline-offset:3px}
svg .bar-lk{cursor:pointer}
svg .bar-lk:hover{opacity:.8}

.more{display:flex;justify-content:center;margin-top:12px}
.more button{font-family:inherit;font-size:11px;font-weight:500;padding:5px 12px;border:1px solid var(--rule);border-radius:5px;
  background:#fff;color:var(--ink);cursor:pointer}
.tb td.n.cl{color:var(--claret)}
.tb td.n + td:not(.n),.tb th.n + th:not(.n){padding-left:18px}
.loading{opacity:.55;transition:opacity .15s}
.ld{padding:60px 0;text-align:center;color:var(--soft);font-size:12px}

@media (max-width:860px){.dn{flex-direction:column;align-items:stretch}.dn svg{margin:0 auto}}
@media (max-width:600px){
  .hrow{flex-wrap:wrap;gap:4px 16px}
  .hs{flex-basis:100%;text-align:left}
  .rk-v em{display:none}
  .rk-n{flex:1 1 0}
  .fsel{min-width:0;width:100%}
  .per{margin-left:0;justify-content:flex-start}
  .sec{flex-wrap:wrap}
}
`;
