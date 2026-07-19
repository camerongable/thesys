module.exports = (output, context) => {
  try {
    const decision = JSON.parse(output);
    return (
      decision.category === context.vars.expected_category &&
      decision.blocked === context.vars.expected_blocked
    );
  } catch {
    return false;
  }
};
