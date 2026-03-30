frappe.provide('bi');
frappe.provide("modifyMethod");

bi.listenForOtp = function (frm,is_bulk=false) {
	// frm will contain listview object if it is bulk_payment, 
	// otherwise it will contain form object. 
	let bulk=""
	if(is_bulk){
		bulk="_bulk"
	}
	frappe.realtime.on("get_bank_otp" + bulk, function(data){

		if (!frm || data.uid != frm._uid || frm.otp_requested) return;

		frm.otp_requested = true;
		frappe.hide_msgprint();

		let msg = data.message || '';
		if (!msg) {
			msg = 'registered mobile number / email address';
		}

		var otp_dialog = frappe.prompt(
			{fieldtype: 'Data', label: 'One Time Password', fieldname: 'otp', reqd: 1,
			 description: (data.message? `${data.message}`:`An OTP has been sent to your ${msg} for further authentication.`)},
		function(_data){
			frappe.call({
				method: "bank_integration.bank_integration.api.continue_with_otp",
				args: {
					otp: _data.otp,
					bank_name: data.bank_name,
					uid: data.uid,
					doctype: frm?.doc?.doctype || frm?.doctype,
					docname: frm?.doc?.name || null,
					logged_in: data.logged_in},
			});
			frappe.msgprint("Verifying OTP!!")
			delete frm.otp_requested;
		}, 'Enter OTP');

		otp_dialog.set_secondary_action(function(){
			frappe.call({
				method: "bank_integration.bank_integration.api.cancel_session",
				args: {bank_name: data.bank_name, logged_in: data.logged_in, uid: data.uid}
			});
			delete frm.otp_requested;
		});
	});
};

bi.listenForQuestions = function (frm) {
	frappe.realtime.on("get_bank_answers", function(data){
		if (!frm || data.uid != frm._uid || frm.answers_requested || !data.questions) return;

		frm.answers_requested = true;
		frappe.hide_msgprint();

		let fields = [];
		for (let [fieldname, label] of Object.entries(data.questions)) {
			fields.push({
				fieldtype: 'Data',
				label: label,
				fieldname: fieldname,
				reqd: 1
			});
		}

		var dialog = frappe.prompt(fields, function(_data){
			frappe.call({
				method: "bank_integration.bank_integration.api.continue_with_answers",
				args: {
					answers: _data,
					bank_name: data.bank_name,
					uid: data.uid,
					doctype: frm.doc.doctype,
					docname: frm.doc.name,
					logged_in: data.logged_in},
			});
			delete frm.answers_requested;
		}, 'Answer Secure Access Questions');

		dialog.set_secondary_action(function(){
			frappe.call({
				method: "bank_integration.bank_integration.api.cancel_session",
				args: {bank_name: data.bank_name, logged_in: data.logged_in, uid: data.uid}
			});
			delete frm.answers_requested;
		});
	});
};

modifyMethod = function (source, funcName, newFunc, before = false) {
  let sourceObj = eval(source);
  if (!sourceObj) {
    console.error(`Could not find object: ${source}`);
    return;
  }
  let isPrototype = false;
  let oldFunc = sourceObj[funcName];

  if (!oldFunc) {
    oldFunc = sourceObj.prototype[funcName];
    isPrototype = true;
  }

  if (!oldFunc) {
    console.error(`Function ${funcName} does not exist for ${source}`);
    return;
  }
  function newFunction() {
    if (before) {
      let msg = newFunc.apply(this, arguments);
      if (msg === "return") {
        return;
      }
    }

    let out = oldFunc.apply(this, arguments);
    let new_out;

    if (!before) {
      let execNewFunc = () => {
        return newFunc.call(this, ...Array.from(arguments), out);
      };
      if (typeof out === "object" && out.then) {
        return out.then(execNewFunc);
      } else {
        new_out = execNewFunc();
      }
    }

    return new_out || out;
  }
  if (isPrototype) {
    sourceObj.prototype[funcName] = newFunction;
  } else {
    sourceObj[funcName] = newFunction;
  }
};
