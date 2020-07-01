(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["meeting-child-row.njk"] = (function() {
function root(env, context, frame, runtime, cb) {
var lineno = 0;
var colno = 0;
var output = "";
try {
var parentTemplate = null;
output += "\r\n";
if(runtime.contextOrFrameLookup(context, frame, "_showedit")) {
output += "\r\n    ";
output += "\r\n    ";
if(!runtime.contextOrFrameLookup(context, frame, "invites")) {
output += "\r\n        ";
output += "\r\n        ";
output += "\r\n        ";
output += "\r\n        <div id=\"childrow-editform\"></div>\r\n\r\n        ";
frame = frame.push();
var t_3 = runtime.contextOrFrameLookup(context, frame, "tables");
if(t_3) {t_3 = runtime.fromIterator(t_3);
var t_2 = t_3.length;
for(var t_1=0; t_1 < t_3.length; t_1++) {
var t_4 = t_3[t_1];
frame.set("t", t_4);
frame.set("loop.index", t_1 + 1);
frame.set("loop.index0", t_1);
frame.set("loop.revindex", t_2 - t_1);
frame.set("loop.revindex0", t_2 - t_1 - 1);
frame.set("loop.first", t_1 === 0);
frame.set("loop.last", t_1 === t_2 - 1);
frame.set("loop.length", t_2);
output += "\r\n            <h2>";
output += runtime.suppressValue(runtime.memberLookup((t_4),"name"), env.opts.autoescape);
output += "</h2>\r\n            <table id=\"childrow-table-";
output += runtime.suppressValue(runtime.memberLookup((t_4),"name"), env.opts.autoescape);
output += "\"></table>\r\n        ";
;
}
}
frame = frame.pop();
output += "\r\n\r\n    ";
output += "\r\n    ";
;
}
else {
output += "\r\n        ";
output += runtime.suppressValue(runtime.contextOrFrameLookup(context, frame, "invites"), env.opts.autoescape);
output += "\r\n    ";
;
}
output += "\r\n\r\n";
output += "\r\n";
;
}
else {
output += "\r\n    <div class=\"childrow-display\">\r\n        ";
if(runtime.contextOrFrameLookup(context, frame, "agendaitem")) {
output += "\r\n            <div class=\"DTE_Label\">Summary</div>\r\n            <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "agendaitem")), env.opts.autoescape);
output += "</div>\r\n        ";
;
}
output += "\r\n        ";
if(runtime.contextOrFrameLookup(context, frame, "discussion")) {
output += "\r\n            <div class=\"DTE_Label\">Discussion</div>\r\n            <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "discussion")), env.opts.autoescape);
output += "</div>\r\n        ";
;
}
output += "\r\n    </div>\r\n    ";
output += "\r\n    ";
frame = frame.push();
var t_7 = runtime.contextOrFrameLookup(context, frame, "tables");
if(t_7) {t_7 = runtime.fromIterator(t_7);
var t_6 = t_7.length;
for(var t_5=0; t_5 < t_7.length; t_5++) {
var t_8 = t_7[t_5];
frame.set("t", t_8);
frame.set("loop.index", t_5 + 1);
frame.set("loop.index0", t_5);
frame.set("loop.revindex", t_6 - t_5);
frame.set("loop.revindex0", t_6 - t_5 - 1);
frame.set("loop.first", t_5 === 0);
frame.set("loop.last", t_5 === t_6 - 1);
frame.set("loop.length", t_6);
output += "\r\n        <h2>";
output += runtime.suppressValue(runtime.memberLookup((t_8),"name"), env.opts.autoescape);
output += "</h2>\r\n        <table id=\"childrow-table-";
output += runtime.suppressValue(runtime.memberLookup((t_8),"name"), env.opts.autoescape);
output += "\"></table>\r\n    ";
;
}
}
frame = frame.pop();
output += "\r\n\r\n";
;
}
if(parentTemplate) {
parentTemplate.rootRenderFunc(env, context, frame, runtime, cb);
} else {
cb(null, output);
}
;
} catch (e) {
  cb(runtime.handleError(e, lineno, colno));
}
}
return {
root: root
};

})();
})();
