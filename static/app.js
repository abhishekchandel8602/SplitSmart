document.querySelectorAll("[data-modal-open]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById(button.dataset.modalOpen)?.classList.add("open");
  });
});

document.querySelectorAll("[data-modal-close]").forEach((button) => {
  button.addEventListener("click", () => button.closest(".modal")?.classList.remove("open"));
});

document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.classList.remove("open");
  });
});

const expenseForm = document.getElementById("expense-form");
if (expenseForm) {
  const methodInputs = expenseForm.querySelectorAll('input[name="split_type"]');
  const valueInputs = expenseForm.querySelectorAll(".share-value");
  const hint = expenseForm.querySelector(".split-hint");

  function updateSplitInputs() {
    const method = expenseForm.querySelector('input[name="split_type"]:checked').value;
    valueInputs.forEach((input) => {
      input.disabled = method === "equal";
      input.placeholder = method === "percentage" ? "%" : method === "exact" ? "Amount" : "";
      if (method === "equal") input.value = "";
    });
    hint.textContent =
      method === "equal"
        ? "Equal split is calculated automatically."
        : method === "percentage"
          ? "Enter percentages that total 100%."
          : "Enter amounts that add up to the expense total.";
  }

  methodInputs.forEach((input) => input.addEventListener("change", updateSplitInputs));
  expenseForm.querySelectorAll('input[name="member_ids"]').forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const valueInput = checkbox.closest(".split-member").querySelector(".share-value");
      valueInput.disabled =
        !checkbox.checked ||
        expenseForm.querySelector('input[name="split_type"]:checked').value === "equal";
      if (!checkbox.checked) valueInput.value = "";
    });
  });
}
