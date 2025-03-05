// Scroll animations
const observers = [];

function createObserver(element, rootMargin = '0px') {
    return new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = 1;
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { rootMargin });
}

// Initialize animations
document.addEventListener('DOMContentLoaded', () => {
    // Animate feature cards
    const featureObserver = createObserver();
    document.querySelectorAll('.feature-card').forEach((element) => {
        element.style.opacity = 0;
        element.style.transform = 'translateY(20px)';
        element.style.transition = 'all 0.6s ease';
        featureObserver.observe(element);
    });

    // Animate footer sections
    const footerObserver = createObserver('0px 0px -100px 0px');
    document.querySelectorAll('.footer-section').forEach((element) => {
        element.style.opacity = 0;
        element.style.transform = 'translateY(20px)';
        element.style.transition = 'all 0.6s ease 0.2s';
        footerObserver.observe(element);
    });

    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
});