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
output += "\r\n    <div id=\"childrow-editform-\" class=\"childrow-editform\"></div>\r\n\r\n";
output += "\r\n";
;
}
else {
output += "\r\n    <div class=\"childrow-display\">\r\n        ";
if(runtime.contextOrFrameLookup(context, frame, "is_hidden") == "yes" && runtime.contextOrFrameLookup(context, frame, "hidden_reason")) {
output += "\r\n            <div class=\"DTE_Label\">HIDDEN: Reason for Hiding</div>\r\n            <div class=\"DTE_Field_Input\"><p>";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "hidden_reason")), env.opts.autoescape);
output += "</p></div>\r\n        ";
;
}
output += "\r\n        ";
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
output += "\r\n    </div>\r\n";
;
}
output += "\r\n\r\n";
output += "\r\n";
output += "\r\n<div class=\"childrow-display\">\r\n    ";
frame = frame.push();
var t_3 = runtime.contextOrFrameLookup(context, frame, "tables");
if(t_3) {t_3 = runtime.fromIterator(t_3);
var t_2 = t_3.length;
for(var t_1=0; t_1 < t_3.length; t_1++) {
var t_4 = t_3[t_1];
frame.set("table", t_4);
frame.set("loop.index", t_1 + 1);
frame.set("loop.index0", t_1);
frame.set("loop.revindex", t_2 - t_1);
frame.set("loop.revindex0", t_2 - t_1 - 1);
frame.set("loop.first", t_1 === 0);
frame.set("loop.last", t_1 === t_2 - 1);
frame.set("loop.length", t_2);
output += "\r\n        <div class=\"DTE_Label\">";
output += runtime.suppressValue(runtime.memberLookup((t_4),"label"), env.opts.autoescape);
output += "</div>\r\n        <table id=\"childrow-table-";
output += runtime.suppressValue(runtime.memberLookup((t_4),"tableid"), env.opts.autoescape);
output += "\"></table>\r\n    ";
;
}
}
frame = frame.pop();
output += "\r\n</div>\r\n";
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
