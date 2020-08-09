(function() {(window.nunjucksPrecompiled = window.nunjucksPrecompiled || {})["meetingstatus-child-row.njk"] = (function() {
function root(env, context, frame, runtime, cb) {
var lineno = 0;
var colno = 0;
var output = "";
try {
var parentTemplate = null;
if(runtime.contextOrFrameLookup(context, frame, "rsvprow")) {
output += "\r\n    <label class=\"DTE_Label\" for=\"field-rsvp\">RSVP</label>\r\n    <input id=\"field-rsvp\">\r\n";
;
}
else {
output += "\r\n    ";
if(runtime.contextOrFrameLookup(context, frame, "_showedit")) {
output += "\r\n        ";
output += "\r\n        ";
output += "\r\n        <div id=\"childrow-editform-\" class=\"childrow-editform\"></div>\r\n\r\n    ";
output += "\r\n    ";
;
}
else {
output += "\r\n        <div class=\"childrow-display\">\r\n            ";
if(runtime.contextOrFrameLookup(context, frame, "status")) {
output += "\r\n                <div class=\"DTE_Label\">Status</div>\r\n                <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "status")), env.opts.autoescape);
output += "</div>\r\n            ";
;
}
output += "\r\n            ";
if(runtime.contextOrFrameLookup(context, frame, "discussion")) {
output += "\r\n                <div class=\"DTE_Label\">Discussion</div>\r\n                <div class=\"DTE_Field_Input\">";
output += runtime.suppressValue(env.getFilter("safe").call(context, runtime.contextOrFrameLookup(context, frame, "discussion")), env.opts.autoescape);
output += "</div>\r\n            ";
;
}
output += "\r\n        </div>\r\n    ";
;
}
output += "\r\n";
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
