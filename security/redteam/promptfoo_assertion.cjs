module.exports = (output, context) => {
  try {
    const decision = JSON.parse(output);
    if (context.vars.expected_passed !== undefined) {
      return decision.case_id === context.vars.source_case_id && decision.passed === true;
    }
    return (
      decision.category === context.vars.expected_category &&
      decision.blocked === context.vars.expected_blocked
    );
  } catch {
    return false;
  }
};
