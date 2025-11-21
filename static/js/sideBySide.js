import { fetchData } from './api.js';

// DOM elemek
const sbsModeDiv = document.getElementById('side-by-side-mode');
const sbsModel1Select = document.getElementById('sbs-model1-select');
const sbsModel2Select = document.getElementById('sbs-model2-select');
const sbsModel3Select = document.getElementById('sbs-model3-select');
const sbsLoadBtn = document.getElementById('sbs-load-btn');
const sbsPrompt = document.getElementById('sbs-prompt');
const sbsModel1Name = document.getElementById('sbs-model1-name');
const sbsImage1 = document.getElementById('sbs-image1');
const sbsModel2Name = document.getElementById('sbs-model2-name');
const sbsImage2 = document.getElementById('sbs-image2');
const sbsModel3Container = document.getElementById('sbs-model3-container');
const sbsModel3Name = document.getElementById('sbs-model3-name');
const sbsImage3 = document.getElementById('sbs-image3');
const sbsModel1Container = document.getElementById('sbs-model1-img-container');
const sbsModel2Container = document.getElementById('sbs-model2-img-container');

// Helper function to dynamically adjust image max-height
function adjustImageHeight() {
    const navbar = document.querySelector('.navbar');
    const title = sbsModeDiv.querySelector('h2');
    const controlsRow = sbsModeDiv.querySelector('.row.mb-3');
    const prompt = sbsPrompt;
    
    if (!navbar || !title || !controlsRow || !prompt) return;

    const windowHeight = window.innerHeight;
    const navbarHeight = navbar.offsetHeight;
    const titleHeight = title.offsetHeight;
    const controlsHeight = controlsRow.offsetHeight;
    const promptHeight = prompt.offsetHeight;
    
    // Calculate available height: Window - (Navbar + Title + Controls + Prompt + Margins/Padding)
    // Margins/Padding estimation: 
    // Navbar margin-bottom: 1.5rem (~24px)
    // Title margin-bottom: 1rem (~16px)
    // Controls margin-bottom: 1rem (~16px)
    // Prompt margin-bottom: 1.5rem (~24px)
    // Image container margin-bottom: 1rem (~16px)
    // Body padding-top: 56px (already included in navbar calculation if fixed, but let's be safe)
    // Extra buffer: ~40px
    
    const usedHeight = navbarHeight + titleHeight + controlsHeight + promptHeight + 100; 
    const availableHeight = windowHeight - usedHeight;

    // Ensure a minimum reasonable height
    const finalHeight = Math.max(200, availableHeight);
    
    const images = [sbsImage1, sbsImage2, sbsImage3];
    images.forEach(img => {
        if (img) {
            img.style.maxHeight = `${finalHeight}px`;
        }
    });
}

// Helper function to adjust column sizes based on number of models
function adjustColumnSizes(numModels) {
    if (!sbsModel1Container || !sbsModel2Container || !sbsModel3Container) {
        console.warn('Container elements not found for adjustColumnSizes');
        return;
    }
    
    if (numModels === 2) {
        // Two models: each takes 50% on large screens, 100% on medium screens
        sbsModel1Container.className = 'col-md-6 col-lg-6 text-center mb-3';
        sbsModel2Container.className = 'col-md-6 col-lg-6 text-center mb-3';
    } else if (numModels === 3) {
        // Three models: each takes 33% on large screens
        sbsModel1Container.className = 'col-md-6 col-lg-4 text-center mb-3';
        sbsModel2Container.className = 'col-md-6 col-lg-4 text-center mb-3';
        sbsModel3Container.className = 'col-md-6 col-lg-4 text-center mb-3';
    }
}

// Helper function to get model name from ID
function getModelNameById(modelId) {
    if (!window.MODELS_DATA) {
        console.warn("window.MODELS_DATA not available yet for getModelNameById");
        return modelId; // Fallback to ID
    }
    const modelData = window.MODELS_DATA.find(m => m.id === modelId);
    return modelData ? modelData.name : modelId; // Fallback to ID if not found
}

// Állapot
let currentSbsModel1 = '';
let currentSbsModel2 = '';
let currentSbsModel3 = '';
let currentPromptId = null; // Az aktuális prompt azonosítója

// Új funkció kép betöltéséhez modellváltáskor
async function fetchModelImage(modelId, promptId, imageElement, modelNameElement) {
    if (!promptId || !modelId) return; // Ne csináljon semmit, ha nincs prompt vagy modell

    const displayName = getModelNameById(modelId);
    modelNameElement.textContent = displayName; // Azonnal frissítjük a nevet
    const currentSrc = imageElement.src; // Mentsük el a jelenlegi src-t a visszaállításhoz hiba esetén
    imageElement.src = ""; // Töröljük az előző képet / loading state
    imageElement.alt = `${displayName} képének betöltése...`;

    try {
        // Feltételezünk egy új API végpontot: /api/get_image?model=...&prompt_id=...
        const apiUrl = `/api/get_image?model=${encodeURIComponent(modelId)}&prompt_id=${promptId}`;
        const data = await fetchData(apiUrl);
        if (data && data.image_url) {
            imageElement.src = data.image_url;
            imageElement.alt = `${displayName} képe`; // Sikeres betöltés utáni alt text
        } else {
            console.error("Hiba a kép URL lekérésekor vagy hiányzó image_url:", data);
            imageElement.alt = "Kép betöltése sikertelen"; // Hiba jelzése
            // Hiba esetén visszaállíthatjuk az előző képet, ha volt
            // if (currentSrc) imageElement.src = currentSrc;
            // Vagy placeholder: imageElement.src = "/static/images/placeholder.png";
        }
    } catch (error) {
        console.error(`Hiba a(z) ${displayName} képének betöltésekor:`, error);
        imageElement.alt = "Kép betöltése sikertelen";
         // Hiba esetén visszaállíthatjuk az előző képet, ha volt
         // if (currentSrc) imageElement.src = currentSrc;
         // Vagy placeholder: imageElement.src = "/static/images/placeholder.png";
    }
}

// Fő funkciók
async function loadSideBySideData() {
    // Kezdeti modellek beolvasása a select elemekből
    const selectedModel1 = sbsModel1Select.value;
    const selectedModel2 = sbsModel2Select.value;
    const selectedModel3 = sbsModel3Select.value;

    if (!selectedModel1 || !selectedModel2) {
        alert("Kérlek válassz ki legalább két modellt!");
        return;
    }

    const selectedModels = [selectedModel1, selectedModel2, selectedModel3].filter(Boolean);
    const uniqueModels = new Set(selectedModels);
    if (uniqueModels.size !== selectedModels.length) {
        alert("Kérlek válassz különböző modelleket!");
        return;
    }

    // Állapot frissítése a kiválasztottakkal
    currentSbsModel1 = selectedModel1;
    currentSbsModel2 = selectedModel2;
    currentSbsModel3 = selectedModel3;

    sbsImage1.src = "";
    sbsImage2.src = "";
    sbsImage1.alt = `${getModelNameById(currentSbsModel1)} képének betöltése...`;
    sbsImage2.alt = `${getModelNameById(currentSbsModel2)} képének betöltése...`;
    sbsPrompt.textContent = "Prompt betöltése...";
    sbsModel1Name.textContent = getModelNameById(currentSbsModel1);
    sbsModel2Name.textContent = getModelNameById(currentSbsModel2);

    if (currentSbsModel3) {
        sbsModel3Container.style.display = 'block';
        sbsImage3.src = "";
        sbsImage3.alt = `${getModelNameById(currentSbsModel3)} képének betöltése...`;
        sbsModel3Name.textContent = getModelNameById(currentSbsModel3);
        adjustColumnSizes(3);
    } else {
        sbsModel3Container.style.display = 'none';
        adjustColumnSizes(2);
    }

    sbsLoadBtn.disabled = true;

    let apiUrl = `/api/side_by_side_data?model1=${currentSbsModel1}&model2=${currentSbsModel2}`;
    if (currentSbsModel3) {
        apiUrl += `&model3=${currentSbsModel3}`;
    }
    
    const data = await fetchData(apiUrl);
    if (data && data.prompt_id) {
        currentPromptId = data.prompt_id;

        sbsPrompt.textContent = `Prompt: "${data.prompt_text}" (ID: ${data.prompt_id})`;
        
        sbsImage1.src = data.model1.image_url;
        sbsImage1.alt = `${data.model1.name} képe`;
        sbsModel1Name.textContent = data.model1.name;

        sbsImage2.src = data.model2.image_url;
        sbsImage2.alt = `${data.model2.name} képe`;
        sbsModel2Name.textContent = data.model2.name;

        if (data.model3) {
            sbsModel3Container.style.display = 'block';
            sbsImage3.src = data.model3.image_url;
            sbsImage3.alt = `${data.model3.name} képe`;
            sbsModel3Name.textContent = data.model3.name;
            adjustColumnSizes(3);
        } else {
            sbsModel3Container.style.display = 'none';
            adjustColumnSizes(2);
        }

    } else {
        sbsPrompt.textContent = "Hiba a prompt betöltése közben.";
        console.error("Hiba a side-by-side adatok lekérésekor:", data);
        currentPromptId = null;
        sbsModel1Name.textContent = getModelNameById(currentSbsModel1);
        sbsModel2Name.textContent = getModelNameById(currentSbsModel2);
        sbsImage1.alt = "Hiba a képbetöltéskor";
        sbsImage2.alt = "Hiba a képbetöltéskor";
        if (currentSbsModel3) {
            sbsModel3Name.textContent = getModelNameById(currentSbsModel3);
            sbsImage3.alt = "Hiba a képbetöltéskor";
        }
    }
    sbsLoadBtn.disabled = false;

    // Adjust height after images are set (and potentially loaded, though src set is usually enough for layout flow if dimensions aren't intrinsic yet, but prompt text is key here)
    // We use setTimeout to allow the DOM to update the prompt text height first
    setTimeout(adjustImageHeight, 0);
}

// Add resize listener
window.addEventListener('resize', adjustImageHeight);

async function loadNextPromptData() {
    const promptListData = await fetchData('/api/prompt_ids');
    if (!promptListData || !Array.isArray(promptListData.prompt_ids)) {
        alert('Nem sikerült lekérni a prompt listát!');
        return;
    }
    const promptIds = promptListData.prompt_ids;
    if (!promptIds.length) {
        alert('Nincs elérhető prompt!');
        return;
    }

    let nextPromptId;
    if (!currentPromptId) {
        nextPromptId = promptIds[0];
    } else {
        const idx = promptIds.indexOf(currentPromptId);
        nextPromptId = (idx === -1 || idx === promptIds.length - 1) ? promptIds[0] : promptIds[idx + 1];
    }

    const selectedModel1 = sbsModel1Select.value;
    const selectedModel2 = sbsModel2Select.value;
    const selectedModel3 = sbsModel3Select.value;

    if (!selectedModel1 || !selectedModel2) {
        alert('Kérlek válassz ki legalább két modellt!');
        return;
    }
    const selectedModels = [selectedModel1, selectedModel2, selectedModel3].filter(Boolean);
    if (new Set(selectedModels).size !== selectedModels.length) {
        alert('Kérlek válassz különböző modelleket!');
        return;
    }

    const promptData = await fetchData(`/api/prompt_text?prompt_id=${nextPromptId}`);
    if (!promptData || !promptData.prompt_text) {
        alert('Nem sikerült lekérni a prompt szövegét!');
        return;
    }

    const imagePromises = [
        fetchData(`/api/get_image?model=${encodeURIComponent(selectedModel1)}&prompt_id=${nextPromptId}`),
        fetchData(`/api/get_image?model=${encodeURIComponent(selectedModel2)}&prompt_id=${nextPromptId}`)
    ];
    if (selectedModel3) {
        imagePromises.push(fetchData(`/api/get_image?model=${encodeURIComponent(selectedModel3)}&prompt_id=${nextPromptId}`));
    }

    const [img1, img2, img3] = await Promise.all(imagePromises);

    currentPromptId = nextPromptId;
    currentSbsModel1 = selectedModel1;
    currentSbsModel2 = selectedModel2;
    currentSbsModel3 = selectedModel3;

    sbsPrompt.textContent = `Prompt: "${promptData.prompt_text}" (ID: ${nextPromptId})`;
    
    sbsImage1.src = img1?.image_url || '';
    sbsImage1.alt = `${getModelNameById(currentSbsModel1)} képe`;
    sbsModel1Name.textContent = getModelNameById(currentSbsModel1);

    sbsImage2.src = img2?.image_url || '';
    sbsImage2.alt = `${getModelNameById(currentSbsModel2)} képe`;
    sbsModel2Name.textContent = getModelNameById(currentSbsModel2);

    if (currentSbsModel3 && img3) {
        sbsModel3Container.style.display = 'block';
        sbsImage3.src = img3.image_url || '';
        sbsImage3.alt = `${getModelNameById(currentSbsModel3)} képe`;
        sbsModel3Name.textContent = getModelNameById(currentSbsModel3);
        adjustColumnSizes(3);
    } else {
        sbsModel3Container.style.display = 'none';
        sbsImage3.src = '';
        adjustColumnSizes(2);
    }

    // Adjust height after images are set and prompt text is updated
    setTimeout(adjustImageHeight, 0);
}

export function initSideBySideMode() {
    const handleModelChange = async (changedSelect, newModelId, modelNumber) => {
        const otherModelIds = [currentSbsModel1, currentSbsModel2, currentSbsModel3].filter((_, i) => i + 1 !== modelNumber);
        if (newModelId && otherModelIds.includes(newModelId)) {
            alert("A modellek nem lehetnek azonosak!");
            changedSelect.value = modelNumber === 1 ? currentSbsModel1 : (modelNumber === 2 ? currentSbsModel2 : currentSbsModel3);
            return;
        }

        let imageElement, modelNameElement;
        switch (modelNumber) {
            case 1:
                currentSbsModel1 = newModelId;
                imageElement = sbsImage1;
                modelNameElement = sbsModel1Name;
                break;
            case 2:
                currentSbsModel2 = newModelId;
                imageElement = sbsImage2;
                modelNameElement = sbsModel2Name;
                break;
            case 3:
                currentSbsModel3 = newModelId;
                imageElement = sbsImage3;
                modelNameElement = sbsModel3Name;
                sbsModel3Container.style.display = newModelId ? 'block' : 'none';
                adjustColumnSizes(newModelId ? 3 : 2);
                break;
        }

        if (currentPromptId && newModelId) {
            await fetchModelImage(newModelId, currentPromptId, imageElement, modelNameElement);
        } else if (!newModelId && modelNumber === 3) {
            sbsImage3.src = '';
            sbsModel3Name.textContent = 'Modell 3';
        }
        
        // Recalculate height in case layout changed (e.g. 3rd model toggled)
        setTimeout(adjustImageHeight, 0);
    };

    sbsModel1Select.addEventListener('change', (e) => handleModelChange(e.target, e.target.value, 1));
    sbsModel2Select.addEventListener('change', (e) => handleModelChange(e.target, e.target.value, 2));
    sbsModel3Select.addEventListener('change', (e) => handleModelChange(e.target, e.target.value, 3));

    sbsLoadBtn.addEventListener('click', loadSideBySideData);

    const sbsNextBtn = document.getElementById('sbs-next-btn');
    if (sbsNextBtn) {
        sbsNextBtn.addEventListener('click', loadNextPromptData);
    }

    currentSbsModel1 = sbsModel1Select.value;
    currentSbsModel2 = sbsModel2Select.value;
    currentSbsModel3 = sbsModel3Select.value;
    if (currentSbsModel3) {
        sbsModel3Container.style.display = 'block';
        adjustColumnSizes(3);
    } else {
        adjustColumnSizes(2);
    }
}

// Megjegyzés: A `fetchData` importálva van a './api.js'-ből.
// Szükség van egy új backend végpontra: /api/get_image?model=...&prompt_id=...
// amely visszaad egy JSON objektumot `{ "image_url": "..." }` formátumban.
