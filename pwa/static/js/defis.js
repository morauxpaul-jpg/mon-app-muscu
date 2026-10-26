/*
 * Formulaire « Lancer un défi » (page Amis, v53). Composant Alpine
 * enregistré par alpine-composants.js (version CSP : pas d'expression
 * dans les attributs, une méthode à la place). Sans JavaScript, le choix
 * de l'exercice reste affiché et le serveur l'ignore hors progression.
 */
window.defiForm = function () {
  return {
    type: "regularite",
    estProgression: function () { return this.type === "progression"; },
  };
};
